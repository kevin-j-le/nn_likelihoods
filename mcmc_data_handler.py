import os
import pickle
import numpy as np
import re
from string import ascii_letters
from datetime import datetime
import argparse

def collect_datasets_diff_evo(in_files = [],
                              out_file = [],
                              burn_in = 5000,
                              n_post_samples_by_param = 10000,
                              sort_ = True,
                              save = True):
    """Function prepares raw mcmc data for plotting"""
    
    # Intialization
    in_files = sorted(in_files)
    tmp = pickle.load(open(in_files[0],'rb'))
    n_param_sets = len(in_files) * len(tmp[2])
    n_param_sets_file = len(tmp[2])
    n_chains = tmp[2][0][0].shape[0]
    n_samples = tmp[2][0][0].shape[1]
    n_params = tmp[2][0][0].shape[2]
    
    # Data containers 
    means = np.zeros((n_param_sets, n_params))
    maps = np.zeros((n_param_sets, n_params))
    orig_params = np.zeros((n_param_sets, n_params))
    r_hat_last = np.zeros((n_param_sets))
    posterior_subsamples = np.zeros((n_param_sets, n_post_samples_by_param, n_params))
    posterior_subsamples_ll = np.zeros((n_param_sets, n_post_samples_by_param))

    file_cnt = 0
    for file_ in in_files:
        # Load datafile in
        tmp_data = pickle.load(open(file_, 'rb'))
        for i in range(n_param_sets_file):
            
            # Extract samples and log likelihood sequences
            tmp_samples = np.reshape(tmp_data[2][i][0][:, burn_in:, :], (-1, n_params))
            tmp_log_l = np.reshape(tmp_data[2][i][1][:, burn_in:], (-1))        
            
            # Fill in return datastructures
            posterior_subsamples[(n_param_sets_file * file_cnt) + i, :, :] = tmp_samples[np.random.choice(tmp_samples.shape[0], size = n_post_samples_by_param), :]
            posterior_subsamples_ll[(n_param_sets_file * file_cnt) + i, :] = tmp_log_l[np.random.choice(tmp_log_l.shape[0], size = n_post_samples_by_param)]
            means[(n_param_sets_file * file_cnt) + i, :] = np.mean(tmp_samples, axis = 0)
            maps[(n_param_sets_file * file_cnt) + i, :] = tmp_samples[np.argmax(tmp_log_l), :]
            orig_params[(n_param_sets_file * file_cnt) + i, :] = tmp_data[0][i, :]
            r_hat_last[(n_param_sets_file * file_cnt) + i] = tmp_data[2][i][2][-1]
            
        print(file_cnt)
        file_cnt += 1
    
    out_dict = {'means': means, 'maps': maps, 'gt': orig_params, 'r_hats': r_hat_last, 'posterior_samples': posterior_subsamples, 'posterior_ll': posterior_subsamples_ll}
    if save == True:
        print('writing to file to ' + out_file)
        pickle.dump(out_dict, open(out_file, 'wb'), protocol = 2)
    
    return out_dict



if __name__ == "__main__":
    CLI = argparse.ArgumentParser()
    CLI.add_argument("--machine",
                     type = str,
                     default = 'x7')
    CLI.add_argument("--method",
                     type = str,
                     default = 'ddm')
    CLI.add_argument("--nburnin",
                    type = int,
                    default = 5000)
    CLI.add_argument("--ndata",
                     type = int,
                     default = 1024)
    CLI.add_argument("--nsubsample",
                     type = int,
                     default = 10000)
    
    args = CLI.parse_args()
    print(args)

    machine = args.machine
    method = args.method
    nburnin = args.nburnin    
    ndata = args.ndata
    nsubsample = args.nsubsample

    if machine == 'home':
        method_comparison_folder = '/Users/afengler/OneDrive/project_nn_likelihoods/data/kde/' + method + '/method_comparison/'
    if machine == 'ccv':
        method_comparison_folder = '/users/afengler/data/kde/' + method + '/method_comparison/'
    if machine == 'x7':
        method_comparison_folder = '/media/data_cifs/afengler/data/kde/' + model + '/method_comparison/'
        
    file_signature = 'post_samp_data_param_recov_unif_reps_1_n_' + str(ndata) + '_1_'
    summary_file = method_comparison_folder + 'summary_' + file_signature[:-1] + '.pickle'
    file_singature_len = len(file_signature)
    files = os.listdir(method_comparison_folder)
    files_ = [method_comparison_folder + file_ for file_ in files if file_[:file_signature_len] == file_signature]
    
    _ = collect_datasets_diff_evo(in_files = files_,
                                  out_file = summary_file,
                                  burn_in = nburnin,
                                  n_post_samples_by_param = nsubsample,
                                  sort_ = True,
                                  save = True)