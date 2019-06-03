# External 
import scipy as scp
#import tensorflow as tf
from scipy.stats import gamma
import numpy as np
#import pandas as pd
#import matplotlib.pyplot as plt
#from sklearn.neighbors import KernelDensity
#import random
#import multiprocessing as mp
#import psutil
#import pickle 
#import os
#import re

# Own
import kde_training_utilities as kde_util
import kde_class as kde
import ddm_data_simulation as ddm_sim

# Collection of boundary functions

# Simulate: RACE MODEL
def my_boundary_race(t = 0, height = 1):
    return height

# Gamma shape: (additive)
def gamma_bnd(t = 1,
              node = 1,
              shape = 1.01,
              scale = 1,
              theta = 0):
    return gamma.pdf(t - node, a = shape, scale = scale)

# Weibull: (additive)
def weibull_bnd(t = 1,
                node = 1,
                shape = 1.01,
                scale = 1,
                theta = 0):
    if t >= node:
        return (shape / scale) * np.power((t - node) / scale, shape - 1) * np.exp( - np.power((t - node) / scale, shape))
    else: 
        return 0

# Exponential decay with decay starting point (multiplicative)
def exp_c1_c2(t = 1, 
              c1 = 1,
              c2 = 1):
    
    b = np.exp(- c2*(t-c1))
    
    if t >= c1:
        
        return b
        
    else:
        return 1
    
# Linear collapse (additive)
def linear_collapse(t = 1, 
                    node = 1,
                    theta = 1):
    if t >= node:
        return (t - node) * (- np.sin(theta) / np.cos(theta))
    else:
        return 0 
    
# Logistic (additive)
def logistic_bound(t = 1,
                   node = 1,
                   k = 1,
                   midpoint = 1,
                   max_val  = 3):
    
    return - (max_val / (1 + np.exp(- k * ((t - midpoint)))))

# Generalized logistic bound (additive)
def generalized_logistic_bnd(t = 1, 
                             B = 2.,
                             M = 3.,
                             v = 0.5):
    return 1 - (1 / np.power(1 + np.exp(- B * (t - M)), 1 / v))