import os
import pickle
import numpy as np
import matplotlib.pyplot as plt
import re
import argparse
import seaborn as sns
import yaml
from string import ascii_letters
import pandas as pd
from pandas.plotting import scatter_matrix
from sklearn.linear_model import LinearRegression
import cddm_data_simulation as cds
import boundary_functions as bf
from datetime import datetime
from statsmodels.distributions.empirical_distribution import ECDF
import scipy as scp

def get_r2_vec(estimates = [0, 0, 0],
               ground_truths = [0, 0, 0]):
    """Function reads in parameter estimates and group truths and returns regression function"""
    r2_vec = []
    for i in range(estimates.shape[1]):
        reg = LinearRegression().fit(np.asmatrix(estimates[:, i]).T, np.asmatrix(ground_truths[:, i]).T)
        r2_vec.append(str(round(reg.score(np.asmatrix(estimates[:, i]).T, np.asmatrix(ground_truths[:, i]).T), 2)))
    return r2_vec

def hdi_eval(posterior_samples = [],
             ground_truths = []):
    
    vec_dim_1 = posterior_samples.shape[0]
    vec_dim_2 = posterior_samples.shape[2]
    
    vec = np.zeros((vec_dim_1, vec_dim_2))

    for i in range(vec_dim_1):
        for j in range(vec_dim_2):
            my_cdf = ECDF(posterior_samples[i, :, j])
            vec[i,j] = my_cdf(ground_truths[i, j])

        if i % 100 == 0:
            print(i)
  
    # Get calibration statistics
    prop_covered_by_param = []
    for i in range(vec.shape[1]):
        prop_covered_by_param.append(np.sum((vec[:, i] > 0.01) * (vec[:, i] < 0.99)) / vec[:, :].shape[0])
    
    prop_covered_all = (vec[:, 0] > 0.01) * (vec[:, 0] < 0.99)
    for i in range(1, vec.shape[1], 1):
        prop_covered_all = prop_covered_all * (vec[:, i] > 0.01) * (vec[:, i] < 0.99)
    prop_covered_all = np.sum(prop_covered_all) / vec.shape[0]
    
    return vec, prop_covered_by_param, prop_covered_all


def sbc_eval(posterior_samples = [],
             ground_truths = []):
    vec_dim_1 = posterior_samples.shape[0]
    vec_dim_2 = posterior_samples.shape[2]
    n_post_samples = posterior_samples.shape[1]
    
    rank_mat = np.zeros((vec_dim_1, vec_dim_2))
    
    for i in range(vec_dim_1):
        for j in range(vec_dim_2):
            samples_tmp = posterior_samples[i, np.random.choice(n_post_samples, size = 100), j]
            samples_tmp.sort()
            rank_mat[i, j] = np.sum(samples_tmp <= ground_truths[i, j])
    return rank_mat

# PREPARE mcmc_dict for plotting

def clean_mcmc_dict(mcmc_dict = {},
                    filter_ = 'choice_p', # 'boundary', 'choice_p' 'none'
                    choice_p_lim = 0.95,
                    param_lims = [],
                    method = []):
    
    # Filter out cases that have choice which are too imbalanced
    
    # Get indices of imbalanced samples
    n_data = mcmc_dict['data'].shape[1]
    n_params = mcmc_dict['data'].shape[0]
    n_choices = np.unique(mcmc_dict['data'][0, :, 1]).shape[0]
    test_choice = np.unique(mcmc_dict['data'][0, : , 1])[0]
    ok_ids = np.zeros(n_params, dtype = np.bool)
    
    if filter_ == 'choice_p':
        if method == 'mlp':
            for i in range(n_params):
                ok_ids[i] = (np.sum(mcmc_dict['data'][i, :, 1] == test_choice) < (n_data * choice_p_lim) and (np.sum(mcmc_dict['data'][i, :, 1] == test_choice) > (n_data * (1 - choice_p_lim))))
        if method == 'cnn':
            for i in range(n_params):
                ok_ids[i] = (np.sum(mcmc_dict['data'][i, :, 1]) < (choice_p_lim) and (np.sum(mcmc_dict['data'][i, :, 1]) > (1 - choice_p_lim)))
                # print(ok_ids[i])
                # print(np.sum(mcmc_dict['data'][i, :, 1]))
            
#             if i == 100:
#                 print(mcmc_dict['data'])
#                 print(mcmc_dict['data'].shape)
#             if not ok_ids[i]:
#                 print('rejected')
                       
    # Filter out severe boundary cases
    if filter_ == 'boundary':
        cnt = 0
        adj_size = 0.1
        for param_bnd_tmp in param_lims:
            if ax_titles[cnt] == 'ndt':
                cnt += 1
            else:
                if cnt == 0:
                    bool_vec = ( mcmc_dict['means'][:, cnt] > param_bnd_tmp[1] - 0.1 ) + ( mcmc_dict['means'][:, cnt] < param_bnd_tmp[0] + 0.1 ) 
                    cnt += 1
                else:
                    bool_vec = (bool_vec + (( mcmc_dict['means'][:, cnt] > param_bnd_tmp[1] - 0.1 ) + ( mcmc_dict['means'][:, cnt] < param_bnd_tmp[0] + 0.1 ))) > 0
                    cnt += 1
            print(np.sum(1 - bool_vec))
        print(np.sum(1 - bool_vec))

        ok_ids = (1 - bool_vec) > 0
        
    if filter_ == 'none':
        ok_ids = (1 - ok_ids) > 0

    for tmp_key in mcmc_dict.keys():
        print(tmp_key)
        #print(np.array(mcmc_dict[tmp_key]))
        mcmc_dict[tmp_key] = np.array(mcmc_dict[tmp_key])[ok_ids]

    # Calulate quantities from posterior samples
    mcmc_dict['sds'] = np.std(mcmc_dict['posterior_samples'][:, :, :], axis = 1)
    mcmc_dict['sds_mean_in_row'] = np.min(mcmc_dict['sds'], axis = 1)
    mcmc_dict['gt_cdf_score'], mcmc_dict['p_covered_by_param'], mcmc_dict['p_covered_all'] = hdi_eval(posterior_samples = mcmc_dict['posterior_samples'],
                                                                                                      ground_truths = mcmc_dict['gt'])
    mcmc_dict['gt_ranks'] = sbc_eval(posterior_samples = mcmc_dict['posterior_samples'],
                                     ground_truths = mcmc_dict['gt'])

    # Get regression coefficients on mcmc_dict 
    mcmc_dict['r2_means'] = get_r2_vec(estimates = mcmc_dict['means'], 
                              ground_truths = mcmc_dict['gt'])

    mcmc_dict['r2_maps'] = get_r2_vec(estimates = mcmc_dict['maps'], 
                              ground_truths = mcmc_dict['gt'])

    #mcmc_dict['gt'][mcmc_dict['r_hats'] < r_hat_cutoff, :]

    mcmc_dict['boundary_rmse'], mcmc_dict['boundary_dist_param_euclid'] = compute_boundary_rmse(mode = 'max_t_global',
                                                                                                boundary_fun = bf.weibull_cdf,
                                                                                                parameters_estimated = mcmc_dict['means'],
                                                                                                parameters_true = mcmc_dict['gt'],
                                                                                                data = mcmc_dict['data'],
                                                                                                model = model,
                                                                                                max_t = 20,
                                                                                                n_probes = 1000)

    mcmc_dict['euc_dist_means_gt'] = np.linalg.norm(mcmc_dict['means'] - mcmc_dict['gt'], axis = 1)
    mcmc_dict['euc_dist_maps_gt'] = np.linalg.norm(mcmc_dict['maps'] - mcmc_dict['gt'], axis = 1)
    mcmc_dict['euc_dist_means_gt_sorted_id'] = np.argsort(mcmc_dict['euc_dist_means_gt'])
    mcmc_dict['euc_dist_maps_gt_sorted_id'] = np.argsort(mcmc_dict['euc_dist_maps_gt'])
    mcmc_dict['boundary_rmse_sorted_id'] = np.argsort(mcmc_dict['boundary_rmse'])
    mcmc_dict['method'] = method
    
    return mcmc_dict

# A of T statistics (considering a of t only for timerange that spans observed data)
def compute_boundary_rmse(mode = 'max_t_global', # max_t_global, max_t_local, quantile
                          boundary_fun = bf.weibull_cdf, # bf.angle etc.
                          parameters_estimated =  [], #mcmc_dict['means'][mcmc_dict['r_hats'] < r_hat_cutoff, :],
                          parameters_true = [], # mcmc_dict['gt'][mcmc_dict['r_hats'] < r_hat_cutoff, :],
                          data = [],
                          model = 'weibull_cdf',
                          max_t = 20,
                          n_probes = 1000):
    

    parameters_estimated_tup = tuple(map(tuple, parameters_estimated[:, 4:]))
    
    #print(parameters_estimated_tup)
    parameters_true_tup = tuple(map(tuple, parameters_true[:, 4:]))
    #t_probes = np.linspace(0, max_t, n_probes)
    bnd_est = np.zeros((len(parameters_estimated), n_probes))
    bnd_true = np.zeros((len(parameters_estimated), n_probes))
    
    # get bound estimates
    for i in range(len(parameters_estimated)):
        #print(parameters_estimated[i])
        max_t = np.max(data[i, :, 0])
        t_probes = np.linspace(0, max_t, n_probes)
        
        if model == 'weibull_cdf' or model == 'weibull_cdf2':
            bnd_est[i] = np.maximum(parameters_estimated[i, 1] * boundary_fun(*(t_probes, ) + parameters_estimated_tup[i]), 0)
            bnd_true[i] = np.maximum(parameters_true[i, 1] * boundary_fun(*(t_probes, ) + parameters_true_tup[i]), 0)
        if model == 'angle':
            bnd_est[i] = np.maximum(parameters_estimated[i, 1] + boundary_fun(*(t_probes, ) + parameters_estimated_tup[i]), 0)
            bnd_true[i] = np.maximum(parameters_true[i, 1] + boundary_fun(*(t_probes, ) + parameters_true_tup[i]), 0)
            #print(parameters_estimated[i, 1] * boundary_fun(*(t_probes, ) + parameters_estimated_tup[i]))
            #print(bnd_true[i])
        else:
            bnd_est[i] = parameters_estimated[i, 1]
            bnd_true[i] = parameters_estimated[i, 1]
            
#         if i % 100 == 0:
#             print(i)
    
    # compute rmse
    rmse_vec = np.zeros((len(parameters_estimated_tup)))
    dist_param_euclid = np.zeros((len(parameters_estimated_tup)))
    for i in range(len(parameters_estimated)):
        rmse_vec[i] = np.sqrt(np.sum(np.square(bnd_est[i] - bnd_true[i])) / n_probes)
        dist_param_euclid[i] = np.sqrt(np.sum(np.square(parameters_estimated[i] - parameters_true[i])))
    
    return rmse_vec, dist_param_euclid

# SUPPORT FUNCTIONS GRAPHS
def parameter_recovery_plot(ax_titles = ['v', 'a', 'w', 'ndt', 'angle'], 
                            title = 'Parameter Recovery: ABC-NN',
                            ground_truths = [0, 0, 0],
                            estimates = [0, 0, 0],
                            estimate_variances = [0, 0, 0],
                            r2_vec = [0, 0, 0],
                            cols = 3,
                            save = True,
                            model = '', 
                            machine = '',
                            method = 'cnn',
                            statistic = 'mean',
                            data_signature = '',
                            train_data_type = ''): # color_param 'none' 
    
    grayscale_map = plt.get_cmap('gray')
    
    normalized_sds = np.zeros(estimates.shape)
    for i in range(estimates.shape[1]):
        normalized_sds[:, i] = (estimate_variances[:, i] - np.min(estimate_variances[:, i])) \
        / (np.max(estimate_variances[:, i]) - np.min(estimate_variances[:, i]))

    rows = int(np.ceil(len(ax_titles) / cols))
    sns.set(style = "white", 
            palette = "muted", 
            color_codes = True)
    
    print('n_rows: ', rows)
    print('n_cols: ', cols)
    
    fig, ax = plt.subplots(rows, 
                           cols, 
                           figsize = (12, 12), 
                           sharex = False, 
                           sharey = False)
    
    fig.suptitle(title, fontsize = 24)
    sns.despine(right = True)

    for i in range(estimates.shape[1]):
        row_tmp = int(np.floor(i / cols))
        col_tmp = i - (cols * row_tmp)
        print('row: ', row_tmp)
        print('col: ', col_tmp)
        sns.regplot(ground_truths[:, i], estimates[:, i], 
                    color = 'black', 
                    marker =  '.',
                    fit_reg = False,
                    ax = ax[row_tmp, col_tmp],
                    scatter_kws = {'s': 120, 'alpha': 0.5, 'color': grayscale_map(normalized_sds[:, i])})
        unity_coords = np.linspace(*ax[row_tmp, col_tmp].get_xlim())
        ax[row_tmp, col_tmp].plot(unity_coords, unity_coords, color = 'red')
        
        # ax.plot(x, x)

        ax[row_tmp, col_tmp].text(0.7, 0.1, '$R^2$: ' + r2_vec[i], 
                                  transform = ax[row_tmp, col_tmp].transAxes, 
                                  fontsize = 14)
        ax[row_tmp, col_tmp].set_xlabel(ax_titles[i] + ' - ground truth', 
                                        fontsize = 16);
        ax[row_tmp, col_tmp].set_ylabel(ax_titles[i] + ' - posterior mean', 
                                        fontsize = 16);
        ax[row_tmp, col_tmp].tick_params(axis = "x", 
                                         labelsize = 14)

    for i in range(estimates.shape[1], rows * cols, 1):
        row_tmp = int(np.floor(i / cols))
        col_tmp = i - (cols * row_tmp)
        ax[row_tmp, col_tmp].axis('off')

    plt.setp(ax, yticks = [])
    
    if save == True:
        if machine == 'home':
            fig_dir = "/users/afengler/OneDrive/git_repos/nn_likelihoods/figures/" + method + "/parameter_recovery"
            if not os.path.isdir(fig_dir):
                os.mkdir(fig_dir)
        
        figure_name = 'parameter_recovery_plot_' + statistic + '_'
        plt.subplots_adjust(top = 0.9)
        plt.subplots_adjust(hspace = 0.3, wspace = 0.3)
        plt.savefig(fig_dir + '/' + figure_name + model + data_signature + '_' + train_data_type + '.png', dpi = 300, )
        plt.close()
    return #plt.show(block = False)

# SUPPORT FUNCTIONS GRAPHS
def parameter_recovery_hist(ax_titles = ['v', 'a', 'w', 'ndt', 'angle'],
                            estimates = [0, 0, 0],
                            r2_vec = [0, 0, 0],
                            cols = 3,
                            save = True,
                            model = '',
                            machine = '',
                            posterior_stat = 'mean', # can be 'mean' or 'map'
                            data_signature = '',
                            train_data_type = '',
                            method = 'cnn'): # color_param 'none' 
    
    rows = int(np.ceil(len(ax_titles) / cols))
    sns.set(style = "white", 
            palette = "muted", 
            color_codes = True)

    fig, ax = plt.subplots(rows, 
                           cols, 
                           figsize = (12, 12), 
                           sharex = False, 
                           sharey = False)
    
    fig.suptitle('Ground truth - Posterior ' + posterior_stat + ': ' + model.upper(), fontsize = 24)
    sns.despine(right = True)

    for i in range(estimates.shape[1]):
        row_tmp = int(np.floor(i / cols))
        col_tmp = i - (cols * row_tmp)

        sns.distplot(estimates[:, i], 
                     color = 'black',
                     bins = 50,
                     kde = False,
                     rug = True,
                     rug_kws = {'alpha': 0.2, 'color': 'grey'},
                     hist_kws = {'alpha': 1, 'range': (-0.5, 0.5), 'edgecolor': 'black'},
                     ax = ax[row_tmp, col_tmp])
        
        ax[row_tmp, col_tmp].axvline(x = 0, linestyle = '--', color = 'red', label = 'ground truth') # ymin=0, ymax=1)
        ax[row_tmp, col_tmp].axvline(x = np.mean(estimates[:, i]), linestyle = '--', color = 'blue', label = 'mean offset')
        
        ax[row_tmp, col_tmp].set_xlabel(ax_titles[i], 
                                        fontsize = 16);
        ax[row_tmp, col_tmp].tick_params(axis = "x", 
                                         labelsize = 14);
        
        if row_tmp == 0 and col_tmp == 0:
            ax[row_tmp, col_tmp].legend(labels = ['ground_truth', 'mean_offset'], fontsize = 14)


    for i in range(estimates.shape[1], rows * cols, 1):
        row_tmp = int(np.floor(i / cols))
        col_tmp = i - (cols * row_tmp)
        ax[row_tmp, col_tmp].axis('off')

    plt.setp(ax, yticks = [])
    
    if save == True:
        if machine == 'home':
            fig_dir = '/users/afengler/OneDrive/git_repos/nn_likelihoods/figures/' + method + '/parameter_recovery'
            if not os.path.isdir(fig_dir):
                os.mkdir(fig_dir)

        figure_name = 'parameter_recovery_hist_'
        plt.subplots_adjust(top = 0.9)
        plt.subplots_adjust(hspace = 0.3, wspace = 0.3)
        plt.savefig(fig_dir + '/' + figure_name + model + data_signature + '_' + train_data_type + '.png', dpi = 300)
        plt.close()
    return #plt.show(block=False)


def posterior_variance_plot(ax_titles = ['v', 'a', 'w', 'ndt', 'angle'], 
                            posterior_variances = [0, 0, 0],
                            cols = 3,
                            save = True,
                            data_signature = '',
                            train_data_type = '',
                            model = '',
                            method = 'cnn',
                            range_max = 0.4):

    rows = int(np.ceil(len(ax_titles) / cols))
    sns.set(style = "white", 
            palette = "muted", 
            color_codes = True)

    fig, ax = plt.subplots(rows, 
                           cols, 
                           figsize = (12, 12), 
                           sharex = False, 
                           sharey = False)
    
    fig.suptitle('Posterior Variance: ' + model.upper(), fontsize = 40)
    sns.despine(right = True)

    for i in range(posterior_variances.shape[1]):
        row_tmp = int(np.floor(i / cols))
        col_tmp = i - (cols * row_tmp)
        
        sns.distplot(posterior_variances[:, i], 
                     color = 'black',
                     bins = 50,
                     kde = False,
                     rug = True,
                     rug_kws = {'alpha': 0.2, 'color': 'grey'},
                     hist_kws = {'alpha': 1, 'range': (0, range_max), 'edgecolor': 'black'},
                     ax = ax[row_tmp, col_tmp])
        
        ax[row_tmp, col_tmp].set_xlabel(ax_titles[i], 
                                        fontsize = 24);
        
        ax[row_tmp, col_tmp].tick_params(axis = "x", 
                                         labelsize = 24);
        

    for i in range(posterior_variances.shape[1], rows * cols, 1):
        row_tmp = int(np.floor(i / cols))
        col_tmp = i - (cols * row_tmp)
        ax[row_tmp, col_tmp].axis('off')

    plt.setp(ax, yticks = [])
    
    if save == True:
        if machine == 'home':
            fig_dir = "/users/afengler/OneDrive/git_repos/nn_likelihoods/figures/" + method + "/posterior_variance"
            if not os.path.isdir(fig_dir):
                os.mkdir(fig_dir)
        
        figure_name = 'posterior_variance_plot_'
        plt.subplots_adjust(top = 0.9)
        plt.subplots_adjust(hspace = 0.3, wspace = 0.3)
        plt.savefig(fig_dir + '/' + figure_name + model + data_signature + '_' + train_data_type + '.png', dpi = 300, )
        plt.close()
    return #plt.show(block = False)


def hdi_p_plot(ax_titles = ['v', 'a', 'w', 'ndt', 'angle'], 
               p_values = [0, 0, 0],
               cols = 3,
               save = True,
               model = '',
               data_signature = '',
               train_data_type = '',
               method = 'cnn'):

    rows = int(np.ceil(len(ax_titles) / cols))
    sns.set(style = "white", 
            palette = "muted", 
            color_codes = True)

    fig, ax = plt.subplots(rows, 
                           cols, 
                           figsize = (12, 12), 
                           sharex = False, 
                           sharey = False)
    
    fig.suptitle('Bayesian p value of ground truth: ' + model.upper(), fontsize = 24)
    sns.despine(right = True)

    for i in range(p_values.shape[1]):
        row_tmp = int(np.floor(i / cols))
        col_tmp = i - (cols * row_tmp)
        
        sns.distplot(p_values[:, i], 
                     bins = 20,
                     color = 'black',
                     kde = False,
                     rug = False,
                     rug_kws = {'alpha': 0.2, 'color': 'grey'},
                     hist_kws = {'alpha': 1, 'edgecolor': 'black'},
                     ax = ax[row_tmp, col_tmp])
        
        ax[row_tmp, col_tmp].set_xlabel(ax_titles[i], 
                                        fontsize = 16);
        
        ax[row_tmp, col_tmp].tick_params(axis = "x", 
                                         labelsize = 14);

    for i in range(p_values.shape[1], rows * cols, 1):
        row_tmp = int(np.floor(i / cols))
        col_tmp = i - (cols * row_tmp)
        ax[row_tmp, col_tmp].axis('off')

    plt.setp(ax, yticks = [])
    
    if save == True:
        if machine == 'home':
            fig_dir = "/users/afengler/OneDrive/git_repos/nn_likelihoods/figures/" + method + "/hdi_p"
            if not os.path.isdir(fig_dir):
                os.mkdir(fig_dir)
                
        figure_name = 'hdi_p_plot_'
        plt.subplots_adjust(top = 0.9)
        plt.subplots_adjust(hspace = 0.3, wspace = 0.3)
        plt.savefig(fig_dir + '/' + figure_name + model + data_signature + '_' + train_data_type + '.png', dpi = 300, )
        plt.close()
    return #plt.show(block = False)

def sbc_plot(ax_titles = ['v', 'a', 'w', 'ndt', 'angle'], 
             ranks = [0, 0, 0],
             cols = 3,
             save = True,
             model = '',
             data_signature = '',
             train_data_type = '',
             method = 'cnn'):

    rows = int(np.ceil(len(ax_titles) / cols))
    sns.set(style = "white", 
            palette = "muted", 
            color_codes = True)

    fig, ax = plt.subplots(rows, 
                           cols, 
                           figsize = (12, 12), 
                           sharex = False, 
                           sharey = False)
    
    fig.suptitle('Bayesian p value of ground truth: ' + model.upper(), fontsize = 24)
    sns.despine(right = True)

    for i in range(ranks.shape[1]):
        row_tmp = int(np.floor(i / cols))
        col_tmp = i - (cols * row_tmp)
        
        sns.distplot(ranks[:, i], 
                     bins = np.arange(0, 101),
                     color = 'black',
                     kde = False,
                     rug = False,
                     rug_kws = {'alpha': 0.2, 'color': 'grey'},
                     hist_kws = {'alpha': 1, 'edgecolor': 'black'},
                     ax = ax[row_tmp, col_tmp])
        
        ax[row_tmp, col_tmp].set_xlabel(ax_titles[i], 
                                        fontsize = 16);
        
        ax[row_tmp, col_tmp].tick_params(axis = "x", 
                                         labelsize = 14);

    for i in range(ranks.shape[1], rows * cols, 1):
        row_tmp = int(np.floor(i / cols))
        col_tmp = i - (cols * row_tmp)
        ax[row_tmp, col_tmp].axis('off')

    plt.setp(ax, yticks = [])
    
    if save == True:
        if machine == 'home':
            fig_dir = "/users/afengler/OneDrive/git_repos/nn_likelihoods/figures/" + method + "/sbc"
            if not os.path.isdir(fig_dir):
                os.mkdir(fig_dir)
                
        figure_name = 'sbc_plot_'
        plt.subplots_adjust(top = 0.9)
        plt.subplots_adjust(hspace = 0.3, 
                            wspace = 0.3)
        plt.savefig(fig_dir + '/' + figure_name + model + data_signature + '_' + train_data_type + '.png', dpi = 300, )
        plt.close()
    return #plt.show(block = False)

def hdi_coverage_plot(ax_titles = [],
                      coverage_probabilities = [],
                      save = True,
                      model = '',
                      data_signature = '',
                      train_data_type = '',
                      method = 'cnn'):
    
    plt.bar(ax_titles, 
            coverage_probabilities,
            color = 'black')
    plt.title( model.upper() + ': Ground truth in HDI?', size = 20)
    plt.xticks(size = 20)
    plt.yticks(np.arange(0, 1, step = 0.2), size = 20)
    plt.ylabel('Prob. HDI covers', size = 20)
    
    if save == True:
        if machine == 'home':
            fig_dir = "/users/afengler/OneDrive/git_repos/nn_likelihoods/figures/" + method + "/hdi_coverage"
            if not os.path.isdir(fig_dir):
                os.mkdir(fig_dir)
        
        figure_name = 'hdi_coverage_plot_'
        plt.savefig(fig_dir + '/' + figure_name + model + data_signature + '_' + train_data_type + '.png', dpi = 300, )
        plt.close()
    return #plt.show(block = False)

def posterior_predictive_plot(ax_titles = [], 
                              title = 'POSTERIOR PREDICTIVES: ',
                              x_labels = [],
                              posterior_samples = [],
                              ground_truths = [],
                              cols = 3,
                              model = 'angle',
                              data_signature = '',
                              train_data_type = '',
                              n_post_params = 100,
                              samples_by_param = 10,
                              save = False,
                              show = False,
                              machine = 'home',
                              method = 'cnn'):
    
    rows = int(np.ceil(len(ax_titles) / cols))
    sns.set(style = "white", 
            palette = "muted", 
            color_codes = True,
            font_scale = 1)

    fig, ax = plt.subplots(rows, cols, 
                           figsize = (12, 12), 
                           sharex = False, 
                           sharey = False)
    fig.suptitle(title + model.upper(), fontsize = 24)
    sns.despine(right = True)

    for i in range(len(ax_titles)):
        row_tmp = int(np.floor(i / cols))
        col_tmp = i - (cols * row_tmp)
        
        post_tmp = np.zeros((n_post_params * samples_by_param, 2))
        idx = np.random.choice(posterior_samples.shape[1], size = n_post_params, replace = False)

        # Run Model simulations for posterior samples
        for j in range(n_post_params):
            if model == 'ddm':
                out = cds.ddm_flexbound(v = posterior_samples[i, idx[j], 0],
                                        a = posterior_samples[i, idx[j], 1],
                                        w = posterior_samples[i, idx[j], 2],
                                        ndt = posterior_samples[i, idx[j], 3],
                                        s = 1,
                                        delta_t = 0.001,
                                        max_t = 20, 
                                        n_samples = samples_by_param,
                                        print_info = False,
                                        boundary_fun = bf.constant,
                                        boundary_multiplicative = True,
                                        boundary_params = {})
                
            if model == 'full_ddm' or model == 'full_ddm2':
                out = cds.full_ddm(v = posterior_samples[i, idx[j], 0],
                                   a = posterior_samples[i, idx[j], 1],
                                   w = posterior_samples[i, idx[j], 2],
                                   ndt = posterior_samples[i, idx[j], 3],
                                   dw = posterior_samples[i, idx[j], 4],
                                   sdv = posterior_samples[i, idx[j], 5],
                                   dndt = posterior_samples[i, idx[j], 6],
                                   s = 1,
                                   delta_t = 0.001,
                                   max_t = 20,
                                   n_samples = samples_by_param,
                                   print_info = False,
                                   boundary_fun = bf.constant,
                                   boundary_multiplicative = True,
                                   boundary_params = {})

            if model == 'angle' or model == 'angle2':
                out = cds.ddm_flexbound(v = posterior_samples[i, idx[j], 0],
                                        a = posterior_samples[i, idx[j], 1],
                                        w = posterior_samples[i, idx[j], 2],
                                        ndt = posterior_samples[i, idx[j], 3],
                                        s = 1,
                                        delta_t = 0.001, 
                                        max_t = 20,
                                        n_samples = samples_by_param,
                                        print_info = False,
                                        boundary_fun = bf.angle,
                                        boundary_multiplicative = False,
                                        boundary_params = {'theta': posterior_samples[i, idx[j], 4]})
            
            if model == 'weibull_cdf' or model == 'weibull_cdf2':
                out = cds.ddm_flexbound(v = posterior_samples[i, idx[j], 0],
                                        a = posterior_samples[i, idx[j], 1],
                                        w = posterior_samples[i, idx[j], 2],
                                        ndt = posterior_samples[i, idx[j], 3],
                                        s = 1,
                                        delta_t = 0.001, 
                                        max_t = 20,
                                        n_samples = samples_by_param,
                                        print_info = False,
                                        boundary_fun = bf.weibull_cdf,
                                        boundary_multiplicative = True,
                                        boundary_params = {'alpha': posterior_samples[i, idx[j], 4],
                                                           'beta': posterior_samples[i, idx[j], 5]})
            if model == 'levy':
                out = cds.levy_flexbound(v = posterior_samples[i, idx[j], 0],
                                         a = posterior_samples[i, idx[j], 1],
                                         w = posterior_samples[i, idx[j], 2],
                                         alpha_diff = posterior_samples[i, idx[j], 3],
                                         ndt = posterior_samples[i, idx[j], 4],
                                         s = 1,
                                         delta_t = 0.001,
                                         max_t = 20,
                                         n_samples = samples_by_param,
                                         print_info = False,
                                         boundary_fun = bf.constant,
                                         boundary_multiplicative = True, 
                                         boundary_params = {})
            
            if model == 'ornstein':
                out = cds.ornstein_uhlenbeck(v = posterior_samples[i, idx[j], 0],
                                             a = posterior_samples[i, idx[j], 1],
                                             w = posterior_samples[i, idx[j], 2],
                                             g = posterior_samples[i, idx[j], 3],
                                             ndt = posterior_samples[i, idx[j], 4],
                                             s = 1,
                                             delta_t = 0.001, 
                                             max_t = 20,
                                             n_samples = samples_by_param,
                                             print_info = False,
                                             boundary_fun = bf.constant,
                                             boundary_multiplicative = True,
                                             boundary_params = {})
            if model == 'ddm_sdv':
                out = cds.ddm_sdv(v = posterior_samples[i, idx[j], 0],
                                  a = posterior_samples[i, idx[j], 1],
                                  w = posterior_samples[i, idx[j], 2],
                                  ndt = posterior_samples[i, idx[j], 3],
                                  sdv = posterior_samples[i, idx[j], 4],
                                  s = 1,
                                  delta_t = 0.001,
                                  max_t = 20,
                                  n_samples = samples_by_param,
                                  print_info = False,
                                  boundary_fun = bf.constant,
                                  boundary_multiplicative = True,
                                  boundary_params = {})
            
            post_tmp[(samples_by_param * j):(samples_by_param * (j + 1)), :] = np.concatenate([out[0], out[1]], axis = 1)
        
        # Run Model simulations for true parameters
        if model == 'ddm':
            out = cds.ddm_flexbound(v = ground_truths[i, 0],
                                    a = ground_truths[i, 1],
                                    w = ground_truths[i, 2],
                                    ndt = ground_truths[i, 3],
                                    s = 1,
                                    delta_t = 0.001,
                                    max_t = 20, 
                                    n_samples = 20000,
                                    print_info = False,
                                    boundary_fun = bf.constant,
                                    boundary_multiplicative = True,
                                    boundary_params = {})

        if model == 'full_ddm' or model == 'full_ddm2':
            out = cds.full_ddm(v = ground_truths[i, 0],
                               a = ground_truths[i, 1],
                               w = ground_truths[i, 2],
                               ndt = ground_truths[i, 3],
                               dw = ground_truths[i, 4],
                               sdv = ground_truths[i, 5],
                               dndt = ground_truths[i, 6],
                               s = 1,
                               delta_t = 0.001,
                               max_t = 20,
                               n_samples = 20000,
                               print_info = False,
                               boundary_fun = bf.constant,
                               boundary_multiplicative = True,
                               boundary_params = {})

        if model == 'angle' or model == 'angle2':
            out = cds.ddm_flexbound(v = ground_truths[i, 0],
                                    a = ground_truths[i, 1],
                                    w = ground_truths[i, 2],
                                    ndt = ground_truths[i, 3],
                                    s = 1,
                                    delta_t = 0.001, 
                                    max_t = 20,
                                    n_samples = 20000,
                                    print_info = False,
                                    boundary_fun = bf.angle,
                                    boundary_multiplicative = False,
                                    boundary_params = {'theta': ground_truths[i, 4]})

        if model == 'weibull_cdf' or model == 'weibull_cdf2':
            out = cds.ddm_flexbound(v = ground_truths[i, 0],
                                    a = ground_truths[i, 1],
                                    w = ground_truths[i, 2],
                                    ndt = ground_truths[i, 3],
                                    s = 1,
                                    delta_t = 0.001, 
                                    max_t = 20,
                                    n_samples = 20000,
                                    print_info = False,
                                    boundary_fun = bf.weibull_cdf,
                                    boundary_multiplicative = True,
                                    boundary_params = {'alpha': ground_truths[i, 4],
                                                       'beta': ground_truths[i, 5]})
        if model == 'levy':
            out = cds.levy_flexbound(v = ground_truths[i, 0],
                                     a = ground_truths[i, 1],
                                     w = ground_truths[i, 2],
                                     alpha_diff = ground_truths[i, 3],
                                     ndt = ground_truths[i, 4],
                                     s = 1,
                                     delta_t = 0.001,
                                     max_t = 20,
                                     n_samples = 20000,
                                     print_info = False,
                                     boundary_fun = bf.constant,
                                     boundary_multiplicative = True, 
                                     boundary_params = {})

        if model == 'ornstein':
            out = cds.ornstein_uhlenbeck(v = ground_truths[i, 0],
                                         a = ground_truths[i, 1],
                                         w = ground_truths[i, 2],
                                         g = ground_truths[i, 3],
                                         ndt = ground_truths[i, 4],
                                         s = 1,
                                         delta_t = 0.001, 
                                         max_t = 20,
                                         n_samples = 20000,
                                         print_info = False,
                                         boundary_fun = bf.constant,
                                         boundary_multiplicative = True,
                                         boundary_params ={})
            
        if model == 'ddm_sdv':
            out = cds.ddm_sdv(v = ground_truths[i, 0],
                              a = ground_truths[i, 1],
                              w = ground_truths[i, 2],
                              ndt = ground_truths[i, 3],
                              sdv = ground_truths[i, 4],
                              s = 1,
                              delta_t = 0.001,
                              max_t = 20,
                              n_samples = 20000,
                              print_info = False,
                              boundary_fun = bf.constant,
                              boundary_multiplicative = True,
                              boundary_params = {})
        
        gt_tmp = np.concatenate([out[0], out[1]], axis = 1)
        print('passed through')
            
        sns.distplot(post_tmp[:, 0] * post_tmp[:, 1], 
                     bins = 50, 
                     kde = False, 
                     rug = False, 
                     hist_kws = {'alpha': 1, 'color': 'black', 'fill': 'black', 'density': 1, 'edgecolor': 'black'},
                     ax = ax[row_tmp, col_tmp]);
        sns.distplot(gt_tmp[:, 0] * gt_tmp[:, 1], 
                     hist_kws = {'alpha': 0.5, 'color': 'grey', 'fill': 'grey', 'density': 1, 'edgecolor': 'grey'}, 
                     bins = 50, 
                     kde = False, 
                     rug = False,
                     ax = ax[row_tmp, col_tmp])
        
        
        if row_tmp == 0 and col_tmp == 0:
            ax[row_tmp, col_tmp].legend(labels = [model, 'posterior'], 
                                        fontsize = 12, loc = 'upper right')
        
        if row_tmp == (rows - 1):
            ax[row_tmp, col_tmp].set_xlabel('RT', 
                                            fontsize = 14);
        
        if col_tmp == 0:
            ax[row_tmp, col_tmp].set_ylabel('Density', 
                                            fontsize = 14);
        
        ax[row_tmp, col_tmp].set_title(ax_titles[i],
                                       fontsize = 16)
        ax[row_tmp, col_tmp].tick_params(axis = 'y', size = 12)
        ax[row_tmp, col_tmp].tick_params(axis = 'x', size = 12)
        
    for i in range(len(ax_titles), rows * cols, 1):
        row_tmp = int(np.floor(i / cols))
        col_tmp = i - (cols * row_tmp)
        ax[row_tmp, col_tmp].axis('off')

    #plt.setp(ax, yticks = [])
    if save == True:
        if machine == 'home':
            fig_dir = "/users/afengler/OneDrive/git_repos/nn_likelihoods/figures/" + method + "/posterior_predictive"
            if not os.path.isdir(fig_dir):
                os.mkdir(fig_dir)
                
        figure_name = 'posterior_predictive_'
        #plt.tight_layout()
        plt.subplots_adjust(top = 0.9)
        plt.subplots_adjust(hspace = 0.3, wspace = 0.3)
        plt.savefig(fig_dir + '/' + figure_name + model + data_signature + '_' + train_data_type + '.png', dpi = 300) #  bbox_inches = 'tight')
        plt.close()
    if show:
        return #plt.show(block = False)

# Posterior predictive RACE / LCA (generally --> n_choices > 2)
def posterior_predictive_plot_race_lca(ax_titles = ['hiconf_go_stnhi.txt',
                                                    'hiconf_go_stnlo.txt',
                                                    'hiconf_go_stnmid.txt',
                                                    'loconf7_go_stnhi.txt',
                                                    'loconf7_go_stnlo.txt',
                                                    'loconf7_go_stnmid.txt'], 
                                        title = 'BG-STN: POSTERIOR PREDICTIVE',
                                        x_labels = [],
                                        posterior_samples = [],
                                        ground_truths = [],
                                        cols = 3,
                                        model = 'angle',
                                        data_signature = '',
                                        n_post_params = 500,
                                        samples_by_param = 10,
                                        show = False,
                                        save = False,
                                        method = [],
                                        train_data_type = ''):

    rows = int(np.ceil(len(ax_titles) / cols))
    print('nrows: ', rows)
    sns.set(style = "white", 
            palette = "muted", 
            color_codes = True,
            font_scale = 2)

    fig, ax = plt.subplots(rows, cols, 
                           figsize = (20, 20), 
                           sharex = False, 
                           sharey = False)
    fig.suptitle(title, fontsize = 40)
    sns.despine(right = True)

    for i in range(len(ax_titles)):
        row_tmp = int(np.floor(i / cols))
        col_tmp = i - (cols * row_tmp)
        
        tmp = np.zeros((n_post_params * samples_by_param, 2))
        idx = np.random.choice(posterior_samples.shape[1], size = n_post_params, replace = False)

        # Run Model simulations
        for j in range(n_post_params):
            # Get posterior model simulations
            if model == 'race_model_3':
                out = cds.race_model(v = np.float32(posterior_samples[i, idx[j], 0:3]),
                                        a = np.float32(posterior_samples[i, idx[j], 3]),
                                        w = np.float32(posterior_samples[i, idx[j], 4:7]),
                                        ndt = np.float32(posterior_samples[i, idx[j], 7]),
                                        s = np.array([1., 1., 1., 1.],dtype=np.float32),
                                        delta_t = 0.001, 
                                        max_t = 10,
                                        n_samples = samples_by_param,
                                        print_info = False,
                                        boundary_fun = bf.constant,
                                        boundary_multiplicative = True,
                                        boundary_params = {})
#             #tmp[(10 * j):(10 * (j + 1)), :] = np.concatenate([out[0], out[1], out[2], out[3]], axis = 1)
#             tmp[(10 * j):(10 * (j + 1)), :] = np.concatenate([out[0], out[1]], axis = 1)
#             #print('posterior samples gathered: ', j')
          
            if model == 'race_model_4':
                out = cds.race_model(v = np.float32(posterior_samples[i, idx[j], 0:4]),
                                        a = np.float32(posterior_samples[i, idx[j], 4]),
                                        w = np.float32(posterior_samples[i, idx[j], 5:9]),
                                        ndt = np.float32(posterior_samples[i, idx[j], 9]),
                                        s = np.array([1., 1., 1., 1.],dtype=np.float32),
                                        delta_t = 0.001, 
                                        max_t = 10,
                                        n_samples = samples_by_param,
                                        print_info = False,
                                        boundary_fun = bf.constant,
                                        boundary_multiplicative = True,
                                        boundary_params = {})
#             #tmp[(10 * j):(10 * (j + 1)), :] = np.concatenate([out[0], out[1], out[2], out[3]], axis = 1)
#             tmp[(10 * j):(10 * (j + 1)), :] = np.concatenate([out[0], out[1]], axis = 1)
#             #print('posterior samples gathered: ', j')
            
            if model == 'lca_3':
                out = cds.lca(v = np.float32(posterior_samples[i, idx[j], 0:3]),
                             a = np.float32(posterior_samples[i, idx[j], 3]),
                             w = np.float32(posterior_samples[i, idx[j], 4:7]),
                             g = np.float32(posterior_samples[i, idx[j], 7]),
                             b = np.float32(posterior_samples[i, idx[j], 8]),
                             ndt = np.float32(posterior_samples[i, idx[j], 9]),
                             #s = np.array([1., 1., 1., 1.],dtype = np.float32),
                             s = 1.0,
                             delta_t = 0.001, 
                             max_t = 10,
                             n_samples = samples_by_param,
                             print_info = False,
                             boundary_fun = bf.constant,
                             boundary_multiplicative = True,
                             boundary_params = {})
                
                if np.std(out[0]) == 0:
                    print(posterior_samples[i, idx[j], :])
                    print(np.mean(out[0]))

            
#             #tmp[(10 * j):(10 * (j + 1)), :] = np.concatenate([out[0], out[1], out[2], out[3]], axis = 1)
#             tmp[(10 * j):(10 * (j + 1)), :] = np.concatenate([out[0], out[1]], axis = 1)
#             #print('posterior samples gathered: ', j')
            
            if model == 'lca_4':
                out = cds.lca(v = np.float32(posterior_samples[i, idx[j], 0:4]),
                              a = np.float32(posterior_samples[i, idx[j], 4]),
                              w = np.float32(posterior_samples[i, idx[j], 5:9]),
                              g = np.float32(posterior_samples[i, idx[j], 9]),
                              b = np.float32(posterior_samples[i, idx[j], 10]),
                              ndt = np.float32(posterior_samples[i, idx[j], 11]),
                              #s = np.array([1., 1., 1., 1.], dtype = np.float32),
                              s = 1.0,
                              delta_t = 0.001,
                              max_t = 10,
                              n_samples = samples_by_param,
                              print_info = False,
                              boundary_fun = bf.constant,
                              boundary_multiplicative = True,
                              boundary_params = {})
                if np.std(out[0]) == 0:
                    print(posterior_samples[i, idx[j], :])
                    print(np.mean(out[0]))

            
            
            #tmp[(10 * j):(10 * (j + 1)), :] = np.concatenate([out[0], out[1], out[2], out[3]], axis = 1)
            tmp[(10 * j):(10 * (j + 1)), :] = np.concatenate([out[0], out[1]], axis = 1)
            #print('posterior samples gathered: ', j')


        # Get model simulations from true data      
        if model == 'race_model_3':
            out = cds.race_model(v = np.float32(ground_truths[i, 0:3]),
                                 a = np.float32(ground_truths[i, 3]),
                                 w = np.float32(ground_truths[i, 4:7]),
                                 ndt = np.float32(ground_truths[i, 7]),
                                 s = np.array([1., 1., 1.], dtype = np.float32),
                                 delta_t = 0.001, 
                                 max_t = 10,
                                 n_samples = 20000,
                                 print_info = False,
                                 boundary_fun = bf.constant,
                                 boundary_multiplicative = True,
                                 boundary_params = {})

        if model == 'race_model_4':
            out = cds.race_model(v = np.float32(ground_truths[i, 0:4]),
                                 a = np.float32(ground_truths[i, 4]),
                                 w = np.float32(ground_truths[i, 5:9]),
                                 ndt = np.float32(ground_truths[i, 9]),
                                 s = np.array([1., 1., 1., 1.],dtype = np.float32),
                                 delta_t = 0.001, 
                                 max_t = 10,
                                 n_samples = 20000,
                                 print_info = False,
                                 boundary_fun = bf.constant,
                                 boundary_multiplicative = True,
                                 boundary_params = {})
            
        if model == 'lca_3':
            out = cds.lca(v = np.float32(ground_truths[i, 0:3]),
                          a = np.float32(ground_truths[i, 3]),
                          w = np.float32(ground_truths[i, 4:7]),
                          g = np.float32(ground_truths[i, 7]),
                          b = np.float32(ground_truths[i, 8]),
                          ndt = np.float32(ground_truths[i, 9]),
                          s = 1.0,
                          #s = np.array([1., 1., 1.],dtype = np.float32),
                          delta_t = 0.001, 
                          max_t = 10,
                          n_samples = 20000,
                          print_info = False,
                          boundary_fun = bf.constant,
                          boundary_multiplicative = True,
                          boundary_params = {})
            
            if np.std(out[0]) == 0:
                print(ground_truths[i, :])
                print(np.mean(out[0]))
                        
            
        if model == 'lca_4':
            out = cds.lca(v = np.float32(ground_truths[i, 0:4]),
                           a = np.float32(ground_truths[i, 4]),
                           w = np.float32(ground_truths[i, 5:9]),
                           g = np.float32(ground_truths[i, 9]),
                           b = np.float32(ground_truths[i, 10]),
                           ndt = np.float32(ground_truths[i, 11]),
                           s = 1.0,
                           #s = np.array([1., 1., 1., 1.],dtype = np.float32),
                           delta_t = 0.001, 
                           max_t = 10,
                           n_samples = 20000,
                           print_info = False,
                           boundary_fun = bf.constant,
                           boundary_multiplicative = True,
                           boundary_params = {})
            
            if np.std(out[0]) == 0:
                print(ground_truths[i, :])   
                print(np.mean(out[0]))
                  

        tmp_true = np.concatenate([out[0], out[1]], axis = 1)
        print('passed through')
        
        plot_colors = ['blue', 'red', 'orange', 'black', 'grey', 'green', 'brown']
        for c in range(6):
            if np.sum(tmp[:, 1] == c) > 0:
                sns.distplot(tmp[np.where(tmp[:, 1] == c)[0], 0], 
                             bins = 50, 
                             hist = False,
                             kde = True, 
                             rug = False, 
                             hist_kws = {'alpha': 0.2, 'color': plot_colors[c], 'density': 1},
                             kde_kws = {'color': plot_colors[c], 'label': 'Ground Truth'},
                             ax = ax[row_tmp, col_tmp])
                sns.distplot(tmp_true[np.where(tmp_true[:, 1] == c)[0], 0], 
                             bins = 50, 
                             hist = False,
                             kde = True, 
                             rug = False, 
                             hist_kws = {'alpha': 0.2, 'color': plot_colors[c], 'density': 1},
                             kde_kws={'linestyle':'--', 'color': plot_colors[c], 'label': 'CNN'},
                             ax = ax[row_tmp, col_tmp])

        if row_tmp == 0 and col_tmp == 0:
            ax[row_tmp, col_tmp].legend(fontsize = 12, loc = 'upper right')
        #    ax[row_tmp, col_tmp].legend(labels = ['Simulations', 'E-D CNN'], fontsize = 20)
        else:
            ax[row_tmp, col_tmp].get_legend().remove()
            
        ax[row_tmp, col_tmp].set_xlabel('', 
                                        fontsize = 24);
        ax[row_tmp, col_tmp].set_ylabel('density', 
                                        fontsize = 24);
        ax[row_tmp, col_tmp].set_title(ax_titles[i],
                                       fontsize = 24)
        ax[row_tmp, col_tmp].tick_params(axis = 'y', size = 24)
        ax[row_tmp, col_tmp].tick_params(axis = 'x', size = 24)
        
    for i in range(ground_truths.shape[0], rows * cols, 1):
        row_tmp = int(np.floor(i / cols))
        col_tmp = i - (cols * row_tmp)
        ax[row_tmp, col_tmp].axis('off')

  #plt.setp(ax, yticks = [])
    if save == True:
        if machine == 'home':
            fig_dir = "/users/afengler/OneDrive/git_repos/nn_likelihoods/figures/" + method + "/posterior_predictive"
            if not os.path.isdir(fig_dir):
                os.mkdir(fig_dir)
                
        figure_name = 'posterior_predictive_'
        #plt.tight_layout()
        plt.subplots_adjust(top = 0.9)
        plt.subplots_adjust(hspace = 0.3, wspace = 0.3)
        plt.savefig(fig_dir + '/' + figure_name + model + data_signature + '_' + train_data_type + '.png', dpi = 300) #  bbox_inches = 'tight')
        plt.close()
    if show:
        return #plt.show(block = False)
  
# Plot bound
# Mean posterior predictives
def boundary_posterior_plot(ax_titles = ['hi-hi', 'hi-lo', 'hi-mid', 'lo-hi', 'lo-mid'], 
                            title = 'Model uncertainty plot: ',
                            posterior_samples = [],
                            ground_truths = [],
                            cols = 3,
                            model = 'weibull_cdf',
                            data_signature = '',
                            train_data_type = '',
                            n_post_params = 500,
                            samples_by_param = 10,
                            max_t = 2,
                            show = True,
                            save = False,
                            machine = 'home',
                            method = 'cnn'):
    
    rows = int(np.ceil(len(ax_titles) / cols))
    sub_idx = np.random.choice(posterior_samples.shape[1], size = n_post_params)
    posterior_samples = posterior_samples[:, sub_idx, :]
    
    sns.set(style = "white", 
            palette = "muted", 
            color_codes = True,
            font_scale = 2)

    fig, ax = plt.subplots(rows, cols, 
                           figsize = (20, 20), 
                           sharex = False, 
                           sharey = False)
    
    my_suptitle = fig.suptitle(title + model, fontsize = 40)
    sns.despine(right = True)
    
    t_s = np.arange(0, max_t, 0.01)
    for i in range(len(ax_titles)):
        row_tmp = int(np.floor(i / cols))
        col_tmp = i - (cols * row_tmp)
        
        idx = np.random.choice(posterior_samples.shape[1], size = n_post_params, replace = False)

        ax[row_tmp, col_tmp].set_xlim(0, max_t)
        ax[row_tmp, col_tmp].set_ylim(-2, 2)
        
        # Run simulations and add histograms
        # True params
        if model == 'angle' or model == 'angle2':
            out = cds.ddm_flexbound(v = ground_truths[i, 0],
                                    a = ground_truths[i, 1],
                                    w = ground_truths[i, 2],
                                    ndt = ground_truths[i, 3],
                                    s = 1,
                                    delta_t = 0.01, 
                                    max_t = 20,
                                    n_samples = 10000,
                                    print_info = False,
                                    boundary_fun = bf.angle,
                                    boundary_multiplicative = False,
                                    boundary_params = {'theta': ground_truths[i, 4]})
            
        if model == 'weibull_cdf' or model == 'weibull_cdf2':
            out = cds.ddm_flexbound(v = ground_truths[i, 0],
                                    a = ground_truths[i, 1],
                                    w = ground_truths[i, 2],
                                    ndt = ground_truths[i, 3],
                                    s = 1,
                                    delta_t = 0.01, 
                                    max_t = 20,
                                    n_samples = 10000,
                                    print_info = False,
                                    boundary_fun = bf.weibull_cdf,
                                    boundary_multiplicative = True,
                                    boundary_params = {'alpha': ground_truths[i, 4],
                                                       'beta': ground_truths[i, 5]})
        
        if model == 'ddm':
            out = cds.ddm_flexbound(v = ground_truths[i, 0],
                                    a = ground_truths[i, 1],
                                    w = ground_truths[i, 2],
                                    ndt = ground_truths[i, 3],
                                    s = 1,
                                    delta_t = 0.01,
                                    max_t = 20, 
                                    n_samples = 10000,
                                    print_info = False,
                                    boundary_fun = bf.constant,
                                    boundary_multiplicative = True,
                                    boundary_params = {})
            
        
        tmp_true = np.concatenate([out[0], out[1]], axis = 1)
        choice_p_up_true = np.sum(tmp_true[:, 1] == 1) / tmp_true.shape[0]
        
        # Run Model simulations for posterior samples
        tmp_post = np.zeros((n_post_params*samples_by_param, 2))
        for j in range(n_post_params):
            if model == 'angle' or model == 'angle2':
                out = cds.ddm_flexbound(v = posterior_samples[i, idx[j], 0],
                                        a = posterior_samples[i, idx[j], 1],
                                        w = posterior_samples[i, idx[j], 2],
                                        ndt = posterior_samples[i, idx[j], 3],
                                        s = 1,
                                        delta_t = 0.01, 
                                        max_t = 20,
                                        n_samples = samples_by_param,
                                        print_info = False,
                                        boundary_fun = bf.angle,
                                        boundary_multiplicative = False,
                                        boundary_params = {'theta': posterior_samples[i, idx[j], 4]})
            
            if model == 'weibull_cdf' or model == 'weibull_cdf2':
                out = cds.ddm_flexbound(v = posterior_samples[i, idx[j], 0],
                                        a = posterior_samples[i, idx[j], 1],
                                        w = posterior_samples[i, idx[j], 2],
                                        ndt = posterior_samples[i, idx[j], 3],
                                        s = 1,
                                        delta_t = 0.01, 
                                        max_t = 20,
                                        n_samples = samples_by_param,
                                        print_info = False,
                                        boundary_fun = bf.weibull_cdf,
                                        boundary_multiplicative = True,
                                        boundary_params = {'alpha': posterior_samples[i, idx[j], 4],
                                                           'beta': posterior_samples[i, idx[j], 5]})
                
            if model == 'ddm':
                out = cds.ddm_flexbound(v = posterior_samples[i, idx[j], 0],
                                        a = posterior_samples[i, idx[j], 1],
                                        w = posterior_samples[i, idx[j], 2],
                                        ndt = posterior_samples[i, idx[j], 3],
                                        s = 1,
                                        delta_t = 0.01,
                                        max_t = 20, 
                                        n_samples = samples_by_param,
                                        print_info = False,
                                        boundary_fun = bf.constant,
                                        boundary_multiplicative = True,
                                        boundary_params = {})
            
            tmp_post[(10 * j):(10 * (j + 1)), :] = np.concatenate([out[0], out[1]], axis = 1)
        
        choice_p_up_post = np.sum(tmp_post[:, 1] == 1) / tmp_post.shape[0]
        
        #ax.set_ylim(-4, 2)
        ax_tmp = ax[row_tmp, col_tmp].twinx()
        ax_tmp.set_ylim(-2, 2)
        ax_tmp.set_yticks([])
        
        counts, bins = np.histogram(tmp_post[tmp_post[:, 1] == 1, 0],
                                    bins = np.linspace(0, 10, 100))
    
        counts_2, bins = np.histogram(tmp_post[tmp_post[:, 1] == 1, 0],
                                      bins = np.linspace(0, 10, 100),
                                      density = True)
        ax_tmp.hist(bins[:-1], 
                    bins, 
                    weights = choice_p_up_post * counts_2,
                    alpha = 0.2, 
                    color = 'black',
                    edgecolor = 'none',
                    zorder = -1)
        
        counts, bins = np.histogram(tmp_true[tmp_true[:, 1] == 1, 0],
                                bins = np.linspace(0, 10, 100))
    
        counts_2, bins = np.histogram(tmp_true[tmp_true[:, 1] == 1, 0],
                                      bins = np.linspace(0, 10, 100),
                                      density = True)
        ax_tmp.hist(bins[:-1], 
                    bins, 
                    weights = choice_p_up_true * counts_2,
                    alpha = 0.2, 
                    color = 'red',
                    edgecolor = 'none',
                    zorder = -1)
        
             
        #ax.invert_xaxis()
        ax_tmp = ax[row_tmp, col_tmp].twinx()
        ax_tmp.set_ylim(2, -2)
        ax_tmp.set_yticks([])
        
        counts, bins = np.histogram(tmp_post[tmp_post[:, 1] == -1, 0],
                        bins = np.linspace(0, 10, 100))
    
        counts_2, bins = np.histogram(tmp_post[tmp_post[:, 1] == -1, 0],
                                      bins = np.linspace(0, 10, 100),
                                      density = True)
        ax_tmp.hist(bins[:-1], 
                    bins, 
                    weights = (1 - choice_p_up_post) * counts_2,
                    alpha = 0.2, 
                    color = 'black',
                    edgecolor = 'none',
                    zorder = -1)
        
        counts, bins = np.histogram(tmp_true[tmp_true[:, 1] == -1, 0],
                                bins = np.linspace(0, 10, 100))
    
        counts_2, bins = np.histogram(tmp_true[tmp_true[:, 1] == -1, 0],
                                      bins = np.linspace(0, 10, 100),
                                      density = True)
        ax_tmp.hist(bins[:-1], 
                    bins, 
                    weights = (1 - choice_p_up_true) * counts_2,
                    alpha = 0.2, 
                    color = 'red',
                    edgecolor = 'none',
                    zorder = -1)
        
        # Plot posterior samples 
        for j in range(n_post_params):
            if model == 'weibull_cdf' or model == 'weibull_cdf2':
                b = posterior_samples[i, idx[j], 1] * bf.weibull_cdf(t = t_s, 
                                                                        alpha = posterior_samples[i, idx[j], 4],
                                                                        beta = posterior_samples[i, idx[j], 5])
            if model == 'angle' or model == 'angle2':
                b = np.maximum(posterior_samples[i, idx[j], 1] + bf.angle(t = t_s, 
                                                                             theta = posterior_samples[i, idx[j], 4]), 0)
            if model == 'ddm':
                b = posterior_samples[i, idx[j], 1] * np.ones(t_s.shape[0])
            
            
            start_point_tmp = - posterior_samples[i, idx[j], 1] + \
                              (2 * posterior_samples[i, idx[j], 1] * posterior_samples[i, idx[j], 2])
            
            slope_tmp = posterior_samples[i, idx[j], 0]
            
            ax[row_tmp, col_tmp].plot(t_s + posterior_samples[i, idx[j], 3], b, 'black',
                                      t_s + posterior_samples[i, idx[j], 3], - b, 'black', 
                                      alpha = 0.05,
                                      zorder = 1000)
            
            for m in range(len(t_s)):
                if (start_point_tmp + (slope_tmp * t_s[m])) > b[m] or (start_point_tmp + (slope_tmp * t_s[m])) < -b[m]:
                    maxid = m
                    break
                maxid = m
            
            ax[row_tmp, col_tmp].plot(t_s[:maxid] + posterior_samples[i, idx[j], 3],
                                      start_point_tmp + slope_tmp * t_s[:maxid], 
                                      'black', 
                                      alpha = 0.05,
                                      zorder = 1000)
            
        # Plot true ground_truths  
        if model == 'weibull_cdf' or model == 'weibull_cdf2':
            b = ground_truths[i, 1] * bf.weibull_cdf(t = t_s, 
                                                     alpha = ground_truths[i, 4],
                                                     beta = ground_truths[i, 5])
            
        if model == 'angle' or model == 'angle2':
            b = np.maximum(ground_truths[i, 1] + bf.angle(t = t_s, theta = ground_truths[i, 4]), 0)
        
        if model == 'ddm':
            b = ground_truths[i, 1] * np.ones(t_s.shape[0])

        start_point_tmp = - ground_truths[i, 1] + \
                          (2 * ground_truths[i, 1] * ground_truths[i, 2])
        slope_tmp = ground_truths[i, 0]

        ax[row_tmp, col_tmp].plot(t_s + ground_truths[i, 3], b, 'red', 
                                  t_s + ground_truths[i, 3], -b, 'red', 
                                  alpha = 1,
                                  linewidth = 3,
                                  zorder = 1000)
        
        for m in range(len(t_s)):
            if (start_point_tmp + (slope_tmp * t_s[m])) > b[m] or (start_point_tmp + (slope_tmp * t_s[m])) < -b[m]:
                maxid = m
                break
            maxid = m
        
        print('maxid', maxid)
        ax[row_tmp, col_tmp].plot(t_s[:maxid] + ground_truths[i, 3], 
                                  start_point_tmp + slope_tmp * t_s[:maxid], 
                                  'red', 
                                  alpha = 1, 
                                  linewidth = 3, 
                                  zorder = 1000)
        
        ax[row_tmp, col_tmp].set_zorder(ax_tmp.get_zorder() + 1)
        ax[row_tmp, col_tmp].patch.set_visible(False)
        print('passed through')
        
        #ax[row_tmp, col_tmp].legend(labels = [model, 'bg_stn'], fontsize = 20)
        if row_tmp == rows:
            ax[row_tmp, col_tmp].set_xlabel('rt', 
                                            fontsize = 20);
        ax[row_tmp, col_tmp].set_ylabel('', 
                                        fontsize = 20);
        ax[row_tmp, col_tmp].set_title(ax_titles[i],
                                       fontsize = 20)
        ax[row_tmp, col_tmp].tick_params(axis = 'y', size = 20)
        ax[row_tmp, col_tmp].tick_params(axis = 'x', size = 20)
        
    for i in range(len(ax_titles), rows * cols, 1):
        row_tmp = int(np.floor(i / cols))
        col_tmp = i - (cols * row_tmp)
        ax[row_tmp, col_tmp].axis('off')
    
    plt.tight_layout(rect = [0, 0.03, 1, 0.9])
    if save:
        if machine == 'home':
            fig_dir = "/users/afengler/OneDrive/git_repos/nn_likelihoods/figures/" + method + "/model_uncertainty"
            if not os.path.isdir(fig_dir):
                os.mkdir(fig_dir)
                
        figure_name = 'model_uncertainty_plot_'
        plt.savefig(fig_dir + '/' + figure_name + model + data_signature + '_' + train_data_type + '.png',
                    dpi = 150, 
                    transparent = False,
                    bbox_inches = 'tight',
                    bbox_extra_artists = [my_suptitle])
        plt.close()
    if show:
        return #plt.show(block = False)
    
def make_posterior_pair_grid(posterior_samples = [],
                             height = 10,
                             aspect = 1,
                             n_subsample = 1000,
                             title = "Posterior Pairwise: ",
                             data_signature = '',
                             train_data_type = '',
                             title_signature= '',
                             gt_available = False,
                             gt = [],
                             save = True,
                             model = None,
                             machine = 'home',
                             method = 'cnn'):
    
    g = sns.PairGrid(posterior_samples.sample(n_subsample), 
                     height = height / len(list(posterior_samples.keys())),
                     aspect = 1,
                     diag_sharey = False)
    g = g.map_diag(sns.kdeplot, color = 'black', shade = True) # shade = True, 
    g = g.map_lower(sns.kdeplot, 
                    shade_lowest = False,
                    n_levels = 30,
                    shade = True, 
                    cmap = 'Greys')
    g = g.map_lower(sns.regplot,
                    color = 'grey',
                    lowess = False,
                    x_ci = None,
                    marker = None,
                    scatter = False,
                    line_kws = {'alpha': 0.5})
    g = g.map_upper(sns.regplot,
                    scatter = True,
                    fit_reg = False,
                    color = 'grey',
                    scatter_kws = {'alpha': 0.01})

    #  g = g.map_upper(sns.scatterplot)
    #  g = g.map_upper(corrdot)
    #  g = g.map_upper(corrfunc)

    [plt.setp(ax.get_xticklabels(), rotation = 45) for ax in g.axes.flat]
    print(g.axes)
    my_suptitle = g.fig.suptitle(title + model.upper() + title_signature, y = 1.03, fontsize = 24)
    
    # If ground truth is available add it in:
    if gt_available:
        for i in range(g.axes.shape[0]):
            for j in range(i + 1, g.axes.shape[0], 1):
                g.axes[i,j].plot(gt[j], gt[i], '.', color = 'red')

        for i in range(g.axes.shape[0]):
            g.axes[i,i].plot(gt[i], g.axes[i,i].get_ylim()[0], '.', color = 'red')

    
    if save == True:
        if machine == 'home':
            fig_dir = "/users/afengler/OneDrive/git_repos/nn_likelihoods/figures/" + method + "/posterior_covariance"
            if not os.path.isdir(fig_dir):
                os.mkdir(fig_dir)
                
        plt.savefig(fig_dir + '/' + 'cov_' + model + data_signature + '_' + train_data_type + '.png', 
                    dpi = 300, 
                    transparent = False,
                    bbox_inches = 'tight',
                    bbox_extra_artists = [my_suptitle])
        plt.close()
    # Show
    return #plt.show(block = False)


if __name__ == "__main__":
    CLI = argparse.ArgumentParser()
    CLI.add_argument("--model",
                     type = str,
                     default = 'ddm')
    CLI.add_argument("--machine",
                     type = str,
                     default = 'home')
    CLI.add_argument("--method",
                     type = str,
                     default = "mlp") # "mlp", "cnn", "navarro"
    CLI.add_argument("--networkidx",
                     type = int,
                     default = -1)
    CLI.add_argument("--traindattype",
                     type = str,
                     default = "kde") # "kde", "analytic"
    CLI.add_argument("--n",
                     type = int,
                     default = 1024)
    CLI.add_argument("--analytic",
                     type = int,
                     default = 0)
    CLI.add_argument("--rhatcutoff",
                     type = float,
                     default = 1.1)
    CLI.add_argument("--npostpred",
                     type = int,
                     default = 9)
    CLI.add_argument("--npostpair",
                     type = int,
                     default = 9)
    CLI.add_argument("--plots",
                     nargs = "*",
                     type = str,
                     default = [])
    CLI.add_argument("--datafilter",
                     type = str,
                     default = 'choice_p')
    
    
    args = CLI.parse_args()
    print(args)
    print(args.plots)
    
    model = args.model
    machine = args.machine
    method = args.method
    n = args.n
    rhatcutoff = args.rhatcutoff
    network_idx = args.networkidx
    traindattype = args.traindattype
    now = datetime.now().strftime("%m_%d_%Y")
    npostpred = args.npostpred
    npostpair = args.npostpair
    datafilter = args.datafilter

# Folder data 
# model = 'ddm_sdv'
# machine = 'home'
# method = 'mlp' # "mlp", "cnn", "navarro"
# n = 4096
# r_hat_cutoff = 1.1
# now = datetime.now().strftime("%m_%d_%Y")
# network_idx = 2
# train_dat = 'analytic'

    # Get model metadata
    info = pickle.load(open('kde_stats.pickle', 'rb'))
    ax_titles = info[model]['param_names'] + info[model]['boundary_param_names']
    print('ax_titles: ', ax_titles)
    print('length ax_titles: ', len(ax_titles))
    param_lims = info[model]['param_bounds_network'] + info[model]['boundary_param_bounds_network']
    
    if method != 'cnn':
        if method != 'navarro':
            with open("model_paths.yaml") as tmp_file:
                if network_idx == -1:
                    network_path = yaml.load(tmp_file)[model]
                    network_id = network_path[list(re.finditer('/', network_path))[-2].end():]
                else:
                    if traindattype == 'analytic':
                        network_path = yaml.load(tmp_file)[model + '_analytic' + '_batch'][network_idx]
                    else:
                        network_path = yaml.load(tmp_file)[model + '_batch'][network_idx]

                    network_id = network_path[list(re.finditer('/', network_path))[-2].end():]


            method_comparison_folder = '/Users/afengler/OneDrive/project_nn_likelihoods/data/' + traindattype + '/' + model + '/method_comparison/' + network_id + '/'

        else:
            method_comparison_folder = '/Users/afengler/OneDrive/project_nn_likelihoods/data/analytic/' + model + '/method_comparison/' + '/analytic/'

        # Get trained networks for model
        file_signature = 'post_samp_data_param_recov_unif_reps_1_n_' + str(n) + '_init_mle_1_'
        summary_file = method_comparison_folder + 'summary_' + file_signature[:-1] + '.pickle'
    else:
        summary_file = '/users/afengler/OneDrive/project_nn_likelihoods/eLIFE_exps/summaries/IS_summary_' + model + '_N_' + str(n) + '.pickle'

    # READ IN SUMMARY FILE
    mcmc_dict = pickle.load(open(summary_file, 'rb'))
    mcmc_dict = clean_mcmc_dict(mcmc_dict = mcmc_dict,
                                filter_ = datafilter,
                                method = method)
    
    # GENERATE PLOTS:
    # POSTERIOR VARIANCE PLOT MLP
    if "posterior_variance" in args.plots:
        print('Making Posterior Variance Plot...')
        posterior_variance_plot(ax_titles = ax_titles, 
                            posterior_variances = mcmc_dict['sds'],
                            cols = 2,
                            save = True,
                            data_signature = '_n_' + str(n) + '_' + now,
                            model = model,
                            method = mcmc_dict['method'],
                            train_data_type = traindattype)
    
    # HDI_COVERAGE PLOT
    if "hdi_coverage" in args.plots:
        print('Making HDI Coverage Plot...')
        hdi_coverage_plot(ax_titles = ax_titles,
                      model = model,
                      coverage_probabilities = mcmc_dict['p_covered_by_param'],
                      data_signature = '_n_' + str(n) + '_' + now,
                      save = True,
                      method = mcmc_dict['method'],
                      train_data_type = traindattype)
    
    # HDI P PLOT
    if "hdi_p" in args.plots:
        print('Making HDI P plot')
        hdi_p_plot(ax_titles = ax_titles,
               p_values = mcmc_dict['gt_cdf_score'],
               cols = 2,
               save = True,
               model = model,
               data_signature = '_n_' + str(n) + '_' + now,
               method = mcmc_dict['method'],
               train_data_type = traindattype)
        
    if "sbc" in args.plots:
        print('Making SBC plot')
        sbc_plot(ax_titles = ax_titles,
                 ranks = mcmc_dict['gt_ranks'],
                 cols = 2,
                 save = True,
                 model = model,
                 data_signature = '_n_' + str(n) + '_' + now,
                 method = mcmc_dict['method'],
                 train_data_type = traindattype)
        
    # PARAMETER RECOVERY PLOTS: KDE MLP
    if "parameter_recovery_scatter" in args.plots:
        print('Making Parameter Recovery Plot...')
        parameter_recovery_plot(ax_titles = ax_titles,
                                title = 'Parameter Recovery: ' + model,
                                ground_truths = mcmc_dict['gt'],
                                estimates = mcmc_dict['means'],
                                estimate_variances = mcmc_dict['sds'],
                                r2_vec = mcmc_dict['r2_means'],
                                cols = 3,
                                save = True,
                                machine = 'home',
                                data_signature = '_n_' + str(n) + '_' + now,
                                method = mcmc_dict['method'],
                                model = model,
                                statistic = 'mean',
                                train_data_type = traindattype)
        
        parameter_recovery_plot(ax_titles = ax_titles,
                                title = 'Parameter Recovery: ' + model,
                                ground_truths = mcmc_dict['gt'],
                                estimates = mcmc_dict['maps'],
                                estimate_variances = mcmc_dict['sds'],
                                r2_vec = mcmc_dict['r2_maps'],
                                cols = 3,
                                save = True,
                                machine = 'home',
                                data_signature = '_n_' + str(n) + '_' + now,
                                method = mcmc_dict['method'],
                                model = model,
                                statistic = 'maps',
                                train_data_type = traindattype)

    
    # Parameter recovery hist MLP
    if "parameter_recovery_hist" in args.plots:
        parameter_recovery_hist(ax_titles = ax_titles,
                                estimates = mcmc_dict['means'] - mcmc_dict['gt'], 
                                cols = 2,
                                save = True,
                                model = model,
                                machine = 'home',
                                posterior_stat = 'mean', # can be 'mean' or 'map'
                                data_signature =  '_n_' + str(n) + '_' + now,
                                method = mcmc_dict['method'],
                                train_data_type = traindattype)
    
    # EUC DIST MEANS GT SORTED ID: MLP
    # n_plots = 9
    # random_idx = np.random.choice(mcmc_dict['gt'][mcmc_dict['r_hats'] < r_hat_cutoff, 0].shape[0], size = n_plots)
    if "posterior_pair" in args.plots:
        print('Making Posterior Pair Plots...')
        idx_vecs = [mcmc_dict['euc_dist_means_gt_sorted_id'][:10], 
                    mcmc_dict['euc_dist_means_gt_sorted_id'][np.arange(int(len(mcmc_dict['euc_dist_means_gt_sorted_id']) / 2 - 5), int(len(mcmc_dict['euc_dist_means_gt_sorted_id']) / 2 + 5), 1)],
                    mcmc_dict['euc_dist_means_gt_sorted_id'][-10:],
                    np.random.choice(mcmc_dict['gt'].shape[0], size = npostpair)]

        data_signatures = ['_n_' + str(n) + '_euc_dist_mean_low_idx_',
                          '_n_' + str(n) + '_euc_dist_mean_medium_idx_',
                          '_n_' + str(n) + '_euc_dist_mean_high_idx_',
                          '_n_' + str(n) + '_euc_dist_mean_random_idx_']

        title_signatures = [', ' + str(n) + ', Recovery Good',
                  ', ' + str(n) + ', Reocvery Medium',
                  ', ' + str(n) + ', Reocvery Bad',
                   ', ' + str(n) + ', Random ID']

        cnt = 0
        tot_cnt = 0
        for idx_vec in idx_vecs:
            for idx in idx_vec:
                print('Making Posterior Pair Plot: ', tot_cnt)
                make_posterior_pair_grid(posterior_samples =  pd.DataFrame(mcmc_dict['posterior_samples'][idx, :, :],
                                                                           columns = ax_titles),
                                         gt =  mcmc_dict['gt'][idx, :],
                                         height = 8,
                                         aspect = 1,
                                         n_subsample = 2000,
                                         data_signature = data_signatures[cnt] + str(idx),
                                         title_signature = title_signatures[cnt],
                                         gt_available = True,
                                         save = True,
                                         model = model,
                                         method = mcmc_dict['method'],
                                         train_data_type = traindattype)
                tot_cnt += 1
            cnt += 1

        
    # MODEL UNCERTAINTY PLOTS
    if "model_uncertainty" in args.plots:
        if model == 'angle' or model == 'weibull_cdf' or model == 'angle2' or model == 'ddm' or model == 'weibull_cdf2':
            print('Making Model Uncertainty Plots...')
            idx_vecs = [mcmc_dict['euc_dist_means_gt_sorted_id'][:npostpred], 
                        mcmc_dict['euc_dist_means_gt_sorted_id'][np.arange(int(len(mcmc_dict['euc_dist_means_gt_sorted_id']) / 2 - 5), int(len(mcmc_dict['euc_dist_means_gt_sorted_id']) / 2 + 5), 1)],
                        mcmc_dict['euc_dist_means_gt_sorted_id'][-npostpred:]]

            data_signatures = ['_n_' + str(n) + '_euc_dist_mean_low_',
                               '_n_' + str(n) + '_euc_dist_mean_medium_',
                               '_n_' + str(n) + '_euc_dist_mean_high_',]

            cnt = 0
            for idx_vec in idx_vecs:
                print('Making Model Uncertainty Plots... sets: ', cnt)
                boundary_posterior_plot(ax_titles = [str(i) for i in idx_vec], 
                                        title = 'Model Uncertainty: ',
                                        posterior_samples = mcmc_dict['posterior_samples'][idx_vec, :, :], # dat_total[1][bottom_idx, 5000:, :],
                                        ground_truths = mcmc_dict['gt'][idx_vec, :], #dat_total[0][bottom_idx, :],
                                        cols = 3,
                                        model = model, # 'weibull_cdf',
                                        data_signature = data_signatures[cnt],
                                        n_post_params = 2000,
                                        samples_by_param = 10,
                                        max_t = 10,
                                        show = True,
                                        save = True,
                                        method = mcmc_dict['method'],
                                        train_data_type = traindattype)
                cnt += 1
            
            
    # POSTERIOR PREDICTIVE PLOTS
    if "posterior_predictive" in args.plots:
        print('Making Posterior Predictive Plots...')
        idx_vecs = [mcmc_dict['euc_dist_means_gt_sorted_id'][:10], 
                    mcmc_dict['euc_dist_means_gt_sorted_id'][np.arange(int(len(mcmc_dict['euc_dist_means_gt_sorted_id']) / 2 - 5), int(len(mcmc_dict['euc_dist_means_gt_sorted_id']) / 2 + 5), 1)],
                    mcmc_dict['euc_dist_means_gt_sorted_id'][-10:]]

        data_signatures = ['_n_' + str(n) + '_euc_dist_mean_low_',
                           '_n_' + str(n) + '_euc_dist_mean_medium_',
                           '_n_' + str(n) + '_euc_dist_mean_high_',]

        cnt = 0
        for idx_vec in idx_vecs:
            print('Making Posterior Predictive Plots... set: ', cnt)
            if 'race' in model or 'lca' in model:
                if cnt != 0 or 'race' in model:
                    posterior_predictive_plot_race_lca(ax_titles = [str(i) for i in idx_vec], 
                                                    title = 'Posterior Predictive',
                                                    x_labels = [],
                                                    posterior_samples = mcmc_dict['posterior_samples'][idx_vec, :, :],
                                                    ground_truths = mcmc_dict['gt'][idx_vec, :],
                                                    cols = 3,
                                                    model = model,
                                                    data_signature = data_signatures[cnt],
                                                    n_post_params = 2000,
                                                    samples_by_param = 10,
                                                    show = True,
                                                    save = True, 
                                                    method = mcmc_dict['method'],
                                                    train_data_type = traindattype)
                                                                
            else:
                posterior_predictive_plot(ax_titles =[str(i) for i in idx_vec],
                                          title = 'Posterior Predictive: ',
                                          posterior_samples = mcmc_dict['posterior_samples'][idx_vec, :, :],
                                          ground_truths =  mcmc_dict['gt'][idx_vec, :],
                                          cols = 3,
                                          model = model,
                                          data_signature = data_signatures[cnt],
                                          n_post_params = 2000,
                                          samples_by_param = 10,
                                          show = True,
                                          save = True,
                                          method = mcmc_dict['method'],
                                          train_data_type = traindattype)
            cnt += 1
