#!/bin/bash
MAX_JOBS=3
GPUS=(1)
TOTAL_GPUS=${#GPUS[@]}

get_gpu_allocation(){
    local job_number=$1
    # Calculate which GPU to allocate based on the job number
    local gpu_id=${GPUS[$((job_number % TOTAL_GPUS))]}
    echo $gpu_id
}

check_jobs(){
    while true; do
        jobs_count=$(jobs -p | wc -l)
        if [ "$jobs_count" -lt "$MAX_JOBS" ]; then
            break
        fi
        sleep 1
    done
}

job_number=0


seed=2024
DATA_ROOT=./dataset
SAVE_ROOT=./output

task_name=soft_sensor
model_name=iTransformer


for seq_len in 16; do
for lr in 0.001; do
for target_idx in "[0,1]"; do
for shift in 1; do
    check_jobs
    # Get GPU allocation for this job
    gpu_allocation=$(get_gpu_allocation $job_number)
    # Increment job number for the next iteration
    ((job_number++))

    {
        # Set CUDA_VISIBLE_DEVICES for this script and run it in the background
        python -u run.py \
            --task_name $task_name \
            --is_training 1 \
            --save_root $SAVE_ROOT \
            --root_path $DATA_ROOT/SRU \
            --data_path SRU_data.txt \
            --model ${model_name} \
            --data SRU \
            --seq_len ${seq_len} \
            --e_layers 2 \
            --d_layers 1 \
            --d_model 128 \
            --d_ff 128 \
            --target_idx ${target_idx} \
            --learning_rate ${lr} \
            --gpu_ids ${gpu_allocation} \
            --rec_lambda 1.0 \
            --auxi_lambda 0.0 \
            --fix_seed ${seed} \
            --train_epochs 1 \
            --patience 10 \
            --lradj none \
            --batch_size 256 \
            --shift ${shift}

        sleep 3
    }
done
done
done
done


wait