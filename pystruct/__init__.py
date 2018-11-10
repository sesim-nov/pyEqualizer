from pystruct.fileops import *
from pystruct.optim import *
from pystruct.regression import *
from matplotlib.pyplot import ioff, savefig, subplots
import sys, getopt
import random 
from time import time
import argparse
import msslhs


def cost_stress(files):
    """
    cost_stress(self, files): Categorize the organisms in a generation by cost based on max stress

    Arguments: 
    files: List of nastran input decks. 
    """
    return [max_cquad_stress(f + ".out") for f in files]

def cost_mass(files):
    """
    cost_mass(files): Categorize organisms by mass. 
    """
    return [mass(f+".out") for f in files]

def uniform_random_force(base_forces, n):
    pre = msslhs.sample(len(base_forces)*2, n, 1)[0].transpose().tolist()
    lhs_exp = make_linear_map(0,104000)
    rand_vals = []
    for i in range(len(pre)):
        p = []
        for j in range(len(pre[i])):
            p.append(lhs_exp(pre[i][j]))
        rand_vals.append(p)
    return random_force_base(base_forces, rand_vals, n)

def normal_random_force(base_forces, n, mu_force, sigma_force, mu_angle, sigma_angle):
    rand_vals_norm = msslhs.sample(len(base_forces)*2, n, 1)[1].transpose().tolist()
    conv_force = make_normal_map(mu_force, sigma_force)
    conv_angle = make_normal_map(mu_angle, sigma_angle)
    rand_vals_out = [ [], [] ]
    for x in range(len(rand_vals_norm[0])):
        if conv_force(rand_vals_norm[0][x]) > 190514:
            vals = rnd_to_actual(conv_force(rand_vals_norm[0][x]), conv_angle(rand_vals_norm[1][x]))
            rand_vals_out[0].append(vals[0])
            rand_vals_out[1].append(vals[1])
    print("Of {} generated systems, {} meet the minimum force criterion.".format(n, len(rand_vals_out[0])))
    return random_force_base(base_forces, rand_vals_out, n)

def rnd_to_actual(force, angle):
    force_vert = force * math.cos(angle)
    force_horiz = force * math.sin(angle)
    return [force_vert, force_horiz]

def random_force_base(base_forces, rand_vals, n):
    """
    random_force(base_forces, n): make an array of random force properties. 

    Parameters: 
    base_forces: The base forces as read from the original file. 
    n: number of random forces to generate. 
    """
    out_vec = []
    for i in range(len(rand_vals[0])):
        out_vec.append([])
        for j in range(len(base_forces)):
            out_vec[i].append(deepcopy(base_forces[j]))
            for k in range(5,7):
                val = rand_vals[2*j + k-5][i]
                out_vec[i][j][k] = to_nas_real(val)
    return out_vec


def plot_inds(ax, inds, lab):
    """
    Plot sets of individuals in a standard way.
    """
    [pt_x, pt_y] = get_plot_pts(inds)
    ax.scatter(pt_x, pt_y, label=lab)
    ax.set_xlabel('Weight(kg)');
    ax.set_ylabel('Stress(MPa)');


def plot_with_front(gen, front, title, fname):
    """
    plot with front: Print the generation gen and front, 
    highlighting front as the pareto front on the graph. 

    Parameters: 
    gen: The generation to plot. 
    front: The pareto front extracted from generation gen
    title: Plot Title
    fname: path to output file for plot image. 
    """
    fig, ax = subplots()
    plot_inds(ax,gen,'Non-Dominant')
    plot_inds(ax,front,'Dominant')
    ax.set_title(title)
    ax.legend()
    fig.savefig(fname)
    return [fig, ax]

def validate_inds(inds, val_force, fname, max_wt, max_stress):
    val_sys = system(99,fname,1,0,[cost_mass, cost_stress],force = val_force)
    val_inds = val_sys.dummy_generation(inds)
    valid_designs = []
    for x in range(len(val_inds)):
        if val_inds[x].fitness[0] < max_wt and val_inds[x].fitness[1] < max_stress:
            valid_designs.append(inds[x])
    return valid_designs

def linspace(lower, upper, length):
    return [lower + x*(upper-lower)/(length-1) for x in range(length)]

def print_ind(ind):
    """
    Compactly print an individual.
    """
    print("Design Spec:")
    print("Top Flange Width:\t\t{}".format(ind.props[0][3]))
    print("Bottom Flange Width:\t\t{}".format(ind.props[1][3]))
    print("Web Thickness:\t\t\t{}".format(ind.props[2][3]))
    print("Doubler Thickness at Hoist Pin:\t{}".format(ind.props[3][3]))
    print("Doubler Thickness at Load Pin:\t{}".format(ind.props[4][3]))

def parseargs():
    """
    Helper function to handle argument parsing
    """
    try:
        parser = argparse.ArgumentParser(description='Differentially optimize a better spreader beam')
        parser.add_argument('--n_gen', '-g', type=int, default=5, help='Number of Simulation Generations')
        parser.add_argument('--n_ind', '-i', type=int, default=15, help='Number of Simulation Individuals') 
        parser.add_argument('--n_sys', '-s', type=int, default=5, help='Number of Simulation Systems')
        parser.add_argument('--max_wt', '-w', type=int, default=1000, help='Maximum Weight Desired' )
        parser.add_argument('--max_stress', '-t', type=int, default=95.3, help='Maximum Stress Desired')
        parser.add_argument('--special' ,'-S' ,help='Perform special case NUM', type=int)
        parser.add_argument('fname') 
        args = parser.parse_args()
        return args
    except:
        raise()

def gen_case(args, force_func):
    N_GEN = args.n_gen           # Number of generations per system. 
    N_IND = args.n_ind           # Number of individuals per system. 
    N_SYS = args.n_sys           # Number of systems. 
    MAX_WT = args.max_wt         # Max Weight
    MAX_STRESS = args.max_stress # Max Stress
    fname = args.fname
    start_time = time()

    # Pull force parameters to randomize
    file_lines = load_from_file(fname)
    starting_force = read_force(file_lines)
    all_front = []
    #Generate random forces
    force_packs = force_func(starting_force, N_SYS)
    print("FORCE PACKS")
    print(force_packs)
    print()

    #For each random force generated...
    for x in range(len(force_packs)):
        main_sys = system(x,fname, 1,N_IND, [cost_mass, cost_stress], force = force_packs[x])
        latest_vec = main_sys.first_generation()
        
        for i in range(N_GEN):
            print("Generation {} in system {} starting at T+ {:.3f}".format(i, x, time()-start_time))
            latest_vec = main_sys.trial_generation(latest_vec)
            latest_props = [a.props for a in latest_vec]
            latest_cost = [a.fitness[0] for a in latest_vec]
            min_cost = min(latest_cost)

            #If any cost values come out to be zero, complain. 
            if min(latest_cost) == 0:
                s = "One or more cost values are zero.\n"
                min_index = latest_cost.index(min_cost)
                min_prop = latest_props[min_index]
                s += "At index {}\n".format(min_index)
                for x in min_prop:
                    s += "{}\n".format(str(x))
                raise ValueError(s)
            print("Generation {} in system {} complete at T+ {:.3f}\n".format(i, x, time()-start_time))

        #Plot results of this system
        front = isolate_pareto(latest_vec)
        _ , _ = plot_with_front(latest_vec, front, 'System {}'.format(str(x)) ,'/tmp/output_sys_' + str(x) + '.png')
        all_front.append(front)

    #Gather all fronts combined. 
    all_front_mixed = []
    for x in all_front:
        for y in x:
            all_front_mixed.append(y)

    #Validate all optimal designs against the maximum load 
    valid_designs = validate_inds(all_front_mixed, starting_force, fname, MAX_WT, MAX_STRESS)

    #Plot regression line
    fig, ax = subplots()
    try:
        mean_line = find_line(all_front_mixed)
        af_x, _ = get_plot_pts(all_front_mixed)
        min_x = min(af_x)
        max_x = max(af_x)
        ml_x = linspace(min_x, max_x, 40)
        ml_y = [mean_line(x) for x in ml_x]
        ax.plot(ml_x, ml_y, 'y-', label='Regression Line')
    except Exception as e:
        print("No regression line printed...")
        print(e)
        raise(e)

    #Generate final selected designs from all paretos. 
    final_front = isolate_pareto(valid_designs)
    
    #Plot each pareto front from each system individually. 
    for x in all_front:
        x_x, x_y = get_plot_pts(x)
        ax.scatter(x_x, x_y, label='System {}'.format(x[0].sys_num))
    #Highlight valid designs
    vd_x, vd_y = get_plot_pts(valid_designs)
    ax.scatter(vd_x, vd_y, label='Valid Designs')
    #Plot final selected designs.
    ff_x, ff_y = get_plot_pts(final_front)
    ax.scatter(ff_x, ff_y, label='Pareto Front')
    

    #Plot axis labels
    ax.legend()
    ax.set_title('All Fronts')
    ax.set_xlabel('Weight(kg)');
    ax.set_ylabel('Stress(MPa)');
    #Save Plot
    fig.savefig('/tmp/all_fronts.png')

    #Summary!
    print("Program Complete.")
    print("Summary of valid designs:")
    for x in range(len(final_front)):
        print("\nSystem {}".format(x))
        print_ind(final_front[x])

def det_run(args):
    print("STUB: Deterministic Run")

def dwu_run(args):
    args_out = deepcopy(args)
    #args_out.n_sys = 1000
    nrf_closed = lambda x,y: normal_random_force(x, y, 150000, 20670, 0, 0.087) #Fix angle and force parameters per our e-mail. 
    gen_case(args_out, nrf_closed)
def main():
    args = parseargs()
    if args.special:
        cases = {
                1: det_run,
                2: dwu_run
                }
        cases[args.special](args)
    else:
        gen_case(args, uniform_random_force)



