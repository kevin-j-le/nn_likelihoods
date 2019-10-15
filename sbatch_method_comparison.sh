#!/bin/bash

# Default resources are 1 core with 2.8GB of memory per core.

# job name:
#SBATCH -J mc_ddm_ndt

# priority
#SBATCH --account=bibs-frankmj-condo

# output file
#SBATCH --output /users/afengler/batch_job_out/method_comparison%A_%a.out

# Request runtime, memory, cores:
#SBATCH --time=24:00:00
#SBATCH --mem=128G
#SBATCH -c 48
#SBATCH -N 1
##SBATCH -p gpu --gres=gpu:1
#SBATCH --array=1-1

# Run a command
#source /users/afengler/miniconda3/etc/profile.d/conda.sh
#conda activate tony
python -u /users/afengler/git_repos/nn_likelihoods/method_comparison_sim.py
