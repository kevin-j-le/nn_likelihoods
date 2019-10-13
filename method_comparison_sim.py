# import tensorflow as tf
# from tensorflow import keras
import numpy as np
import yaml
import pandas as pd
from itertools import product
from samplers import SliceSampler
import pickle
import uuid

import boundary_functions as bf
import multiprocessing as mp
import cddm_data_simulation as cd
from cdwiener import batch_fptd
import clba

import keras_to_numpy as ktnp

# INITIALIZATIONS -------------------------------------------------------------
machine = 'ccv'
method = 'lba_analytic'
analytic = True
file_signature = '_start_true_'
n_data_samples = 2500
n_slice_samples = 10000
n_sims = 10
n_cpus = 'all'

if machine == 'x7':
    stats = pickle.load(open("/media/data_cifs/afengler/git_repos/nn_likelihoods/kde_stats.pickle", "rb"))
    method_params = stats[method]
    output_folder = method_params['output_folder_x7']
    with open("model_paths_x7.yaml") as tmp_file:
        network_path = yaml.load(tmp_file)[method]
if machine == 'ccv':
    stats = pickle.load(open("/users/afengler/git_repos/nn_likelihoods/kde_stats.pickle", "rb"))
    method_params = stats[method]
    output_folder = method_params['output_folder']
    with open("model_paths.yaml") as tmp_file:
        network_path = yaml.load(tmp_file)[method]
        
print(stats)
print(method_params)
# Load weights, biases and activations of current network --------
if analytic:
    pass
else:
    with open(network_path + "weights.pickle", "rb") as tmp_file:
        weights = pickle.load(tmp_file)
    with open(network_path + 'biases.pickle', 'rb') as tmp_file:
        biases = pickle.load(tmp_file)
    with open(network_path + 'activations.pickle', 'rb') as tmp_file:
        activations = pickle.load(tmp_file)
# ----------------------------------------------------------------

# DEFINE TARGET LIKELIHOODS FOR CORRESPONDING MODELS -------------------------------------------------

# MLP TARGET
def mlp_target(params, data, likelihood_min = 1e-7): 
    ll_min = np.log(likelihood_min)
    params_rep = np.tile(params, (data.shape[0], 1))
    input_batch = np.concatenate([params_rep, data], axis = 1)
    out = np.maximum(ktnp.predict(input_batch, weights, biases, activations), ll_min)
    return np.sum(out)

# NAVARRO FUSS (DDM)
def nf_target(params, data, likelihood_min = 1e-16):
    return np.sum(np.maximum(np.log(batch_fptd(data[:, 0] * data[:, 1] * (- 1),
                                        params[0],
                                        params[1] * 2, 
                                        params[2],
                                        params[3])), np.log(likelihood_min)))

# LBA ANALYTIC 
def lba_target(params, data):
    return clba.batch_dlba2(rt = data[:, 0], 
                            choice = data[:, 1], 
                            v = params[:2],
                            A = params[2], 
                            b = params[3], 
                            s = params[4],
                            ndt = params[5])

# ----------------------------------------------------------------------------------------------------

# MAKE PARAMETER / DATA GRID -------------------------------------------------------------------------

# REFORMULATE param bounds
def generate_param_grid():
    param_upper_bnd = []
    param_lower_bnd = []
    boundary_param_upper_bnd = [] 
    boundary_param_lower_bnd = []

    for p in range(len(method_params['param_names'])):
        param_upper_bnd.append(method_params['param_bounds_sampler'][p][1])
        param_lower_bnd.append(method_params['param_bounds_sampler'][p][0])

    if len(method_params['boundary_param_names']) > 0:
        for p in range(len(method_params['boundary_param_names'])):
            boundary_param_upper_bnd.append(method_params['boundary_param_bounds'][p][1])
            boundary_param_lower_bnd.append(method_params['boundary_param_bounds'][p][0])                                    

    param_grid = np.random.uniform(low = param_lower_bnd, 
                                   high = param_upper_bnd, 
                                   size = (n_sims, len(method_params['param_names'])))

    if len(method_params['boundary_param_names']) > 0:
        boundary_param_grid = np.random.uniform(low = boundary_param_lower_bnd,
                                                high = boundary_param_upper_bnd,
                                                size = (n_sims, len(method_params['boundary_param_bounds'])))
    else:
        boundary_param_grid = []
        
    return (param_grid, boundary_param_grid)

# REFORMULATE param bounds
def generate_param_grid_lba2():
    param_upper_bnd = []
    param_lower_bnd = []
    boundary_param_upper_bnd = [] 
    boundary_param_lower_bnd = []

    for p in range(len(method_params['param_names'])):
        param_upper_bnd.append(method_params['param_bounds_sampler'][p][1])
        param_lower_bnd.append(method_params['param_bounds_sampler'][p][0])

    if len(method_params['boundary_param_names']) > 0:
        for p in range(len(method_params['boundary_param_names'])):
            boundary_param_upper_bnd.append(method_params['boundary_param_bounds'][p][1])
            boundary_param_lower_bnd.append(method_params['boundary_param_bounds'][p][0])                                    

    param_grid = np.random.uniform(low = param_lower_bnd, 
                                   high = param_upper_bnd, 
                                   size = (n_sims, len(method_params['param_names'])))
    
    # Adjust v_1 so that we are unlikely to get not observations for either choice
    # Works only for two choices
    param_grid[:, 1] = param_grid[:, 0] + (param_grid[:, 4] * np.random.uniform(low = - 2.0, high = 2.0, size = n_sims))

    if len(method_params['boundary_param_names']) > 0:
        boundary_param_grid = np.random.uniform(low = boundary_param_lower_bnd,
                                                high = boundary_param_upper_bnd,
                                                size = (n_sims, len(method_params['boundary_param_bounds'])))
    else:
        boundary_param_grid = []
        
    return param_grid
                     
def generate_data_grid(param_grid, boundary_param_grid):
    data_grid = np.zeros((n_sims, n_data_samples, 2))
    for i in range(n_sims):
        param_dict_tmp = dict(zip(method_params["param_names"], param_grid[i]))
        
        if len(method_params['boundary_param_names']) > 0:
            boundary_dict_tmp = dict(zip(method_params["boundary_param_names"], boundary_param_grid[i]))
        else:
            boundary_dict_tmp = {}
            
        rts, choices, _ = method_params["dgp"](**param_dict_tmp, 
                                               boundary_fun = method_params["boundary"], 
                                               n_samples = n_data_samples,
                                               delta_t = 0.01, 
                                               boundary_params = boundary_dict_tmp,
                                               boundary_multiplicative = method_params['boundary_multiplicative'])
        
        data_grid[i] = np.concatenate([rts, choices], axis = 1)
    return data_grid

def generate_data_grid_lba2(param_grid):
    data_grid = np.zeros((n_sims, n_data_samples, 2))
    param_names_tmp = ['v', 'A', 'b', 's', 'ndt']
    for i in range(n_sims):
        params_tmp = []
        params_tmp.append(np.array(param_grid[i][:2]))
        params_tmp.append(np.array(param_grid[i][2]))
        params_tmp.append(np.array(param_grid[i][3]))
        params_tmp.append(np.array(param_grid[i][4])) 
        params_tmp.append(np.array(param_grid[i][5]))
        params_dict_tmp = dict(zip(param_names_tmp, params_tmp))
        print('params_dict: ', params_dict_tmp)
        # Generate data
        rts, choices, _ = method_params["dgp"](**params_dict_tmp,
                                               n_samples = n_data_samples)
        data_grid[i] = np.concatenate([rts, choices], axis = 1)
    return data_grid


if method[:3] == 'lba':
    param_grid = generate_param_grid_lba2()
    data_grid = generate_data_grid_lba2(param_grid) 
else:   
    param_grid, boundary_param_grid = generate_param_grid() 
    data_grid = generate_data_grid(param_grid, boundary_param_grid)
    if len(method_params['boundary_param_names']) > 0:
        param_grid = np.concatenate([param_grid, boundary_param_grid], axis = 1)

print('param_grid: ', param_grid)
#print(data_grid)
print('shape of data_grid:', data_grid.shape)
# ----------------------------------------------------------------------------------------------------

# RUN POSTERIOR SIMULATIONS --------------------------------------------------------------------------

# Get full parameter vector including bounds
if method[:3] == 'lba':
    sampler_param_bounds = np.array(method_params["param_bounds_sampler"] + method_params["boundary_param_bounds"])
else:
    sampler_param_bounds = np.array(method_params["param_bounds_sampler"] + method_params["boundary_param_bounds"])

# Define posterior samplers for respective likelihood functions
def mlp_posterior(args): # args = (data, true_params)
    model = SliceSampler(bounds = sampler_param_bounds, 
                         target = mlp_target, 
                         w = .4 / 1024, 
                         p = 8)
    model.sample(args[0], num_samples = n_slice_samples, init = args[1])
    return model.samples

#test navarro-fuss
def nf_posterior(args):
    model = SliceSampler(bounds = sampler_param_bounds,
                         target = nf_target, 
                         w = .4 / 1024, 
                         p = 8)
    model.sample(args[0], num_samples = n_slice_samples, init = args[1])
    return model.samples

def lba_posterior(args):
    model = SliceSampler(bounds = sampler_param_bounds,
                         target = lba_target,
                         w = .4 / 1024,
                         p = 8)
    model.sample(args[0], num_samples = n_slice_samples, init = args[1])
    return model.samples

# Make available the specified amount of cpus
if n_cpus == 'all':
    p = mp.Pool(mp.cpu_count())
    
else: 
    p = mp.Pool(n_cpus)

# Run the sampler with correct target as specified above
if method == 'lba_analytic':
    kde_results = np.array(p.map(lba_posterior, zip(data_grid, param_grid)))
elif method == 'ddm_analytic':
    kde_results = np.array(p.map(nf_posterior, zip(data_grid, param_grid)))
else:
    kde_results = np.array(p.map(mlp_posterior, zip(data_grid, param_grid)))

# Store files
pickle.dump((param_grid, data_grid, kde_results), 
            open(output_folder + "kde_sim_test_ndt" + file_signature + "{}.pickle".format(uuid.uuid1()), "wb"))
