#!/bin/bash

# SLURM INSTRUCTIONS IF RUN AS SBATCH JOB ---------------------------

# job name:
#SBATCH -J ornstein_sim

# priority
#SBATCH --account=bibs-frankmj-condo

# output file
#SBATCH --output /users/afengler/batch_job_out/ornstein_sim_%A_%a.out

# Request runtime, memory, cores:
#SBATCH --time=36:00:00
#SBATCH --mem=32G
#SBATCH -c 14
#SBATCH -N 1
#SBATCH --array=1-100
# --------------------------------------------------------------------

# INITIALIZATIONS ----------------------------------------------------
declare -a dgps=( "ddm" "angle" "weibull_cdf")
n_samples=( 50 100 1000 2000 ) # 200 400 800 1600 3200 6400 ) #( 50000 100000 200000 400000 )
n_choices=( 2 ) # 3 4 5 6 ) #4 5 6 )
n_parameter_sets=10  #20000
n_subjects=( 5 10 20 )
n_bins=( 0 )
binned=0
mode='mlp'
datatype='parameter_recovery_hierarchical'
machine='other' # 'home' (alex laptop), 'ccv' (oscar), 'x7' (serrelab), 'other' (makes folders in this repo)
maxt=20
# ---------------------------------------------------------------------


# DATA GENERATION LOOP ------------------------------------------------

for bins in "${n_bins[@]}"
do
    for n in "${n_samples[@]}"
    do
        for dgp in "${dgps[@]}"
        do
            for n_c in "${n_choices[@]}"
            do
                for n_s in "${n_subjects[@]}"
                    do
                       echo "$dgp"
                       echo $n_c
                       python -u dataset_generator.py --machine $machine --dgplist $dgp --datatype $datatype --nreps 1 --binned $binned --nbins $bins --maxt $maxt --nchoices $n_c --nsamples $n --mode $mode --nparamsets $n_parameter_sets --save 1 --maxt $maxt --nsubjects $n_s
                    done
            done
        done
    done
done

# -----------------------------------------------------------------------