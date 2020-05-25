#!/bin/bash

# Default resources are 1 core with 2.8GB of memory per core.

# job name:
#SBATCH -J sdv_analy

# priority
##SBATCH --account=bibs-frankmj-condo
#SBATCH --account=carney-frankmj-condo
##SBATCH --account=bibs-frankmj-condo

# output file
#SBATCH --output /users/afengler/batch_job_out/meth_comp_%A_%a.out

# Request runtime, memory, cores:
#SBATCH --time=24:00:00
#SBATCH --mem=32G
#SBATCH -c 12
#SBATCH -N 1
#SBATCH -p gpu --gres=gpu:1
#SBATCH --array=1-1

# Run a command
#source /users/afengler/miniconda3/etc/profile.d/conda.sh
#conda activate tony

# source /users/afengler/.bashrc
# conda deactivate
# conda activate tf-cpu

source /users/afengler/.bashrc
conda deactivate
conda activate tf-gpu-py37


# NNBATCH RUNS

nmcmcsamples=25000
nbyarrayjob=10
ncpus=1
nsamples=( 1024 ) #( 1024 2048 4096 ) # 2048 4096 ) #( 1024 2048 4096 )
method="ddm_analytic" #'ddm_sdv_analytic'   #'ddm_sdv_analytic'  #"full_ddm2"
ids=( 2 )
machine='ccv'
samplerinit='random'
analytic=0
#SLURM_ARRAY_TASK_ID=1

for n in "${nsamples[@]}"
do
    for id in "${ids[@]}"
    do 
        python -u method_comparison_sim.py --machine $machine --method $method --nsamples $n --nmcmcsamples $nmcmcsamples --datatype parameter_recovery --sampler diffevo --infileid 1 --boundmode train --outfilesig _expanded_bounds_test --outfileid $SLURM_ARRAY_TASK_ID --activedims 0 1 2 3 4 --samplerinit $samplerinit --ncpus $ncpus --nbyarrayjob $nbyarrayjob --nnbatchid $id --analytic $analytic
    done
done

