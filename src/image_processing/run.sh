#!/bin/bash


python3 -m venv scalable_env
source ./scalable_env/bin/activate

pip3 install -r requriements.txt


# to generate
python src/image_processing/generate.py --width 128 --height 64 --length 4 --symbols symbols.txt --count 3200 --output-dir test


# to train
python train.py --width 128 --height 64 --length 4 --symbols symbols.txt --batch-size 32 --epochs 5 --output-model test.h5 --train-dataset training_data --validate-dataset validation_data


# to predict 
python classify.py --model-name test --captcha-dir validation_data --output output.txt --symbols symbols.txt
