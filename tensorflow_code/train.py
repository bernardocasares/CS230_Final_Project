"""Train the model."""

import argparse
import logging
import os
import pandas as pd
import random

import tensorflow as tf

from model.input_fn import input_fn
from model.utils import Params
from model.utils import set_logger
from model.utils import save_dict_to_json
from model.model_fn import model_fn
from model.training import train_and_evaluate


parser = argparse.ArgumentParser()
parser.add_argument('--model_dir', default='experiments/learning_rate',
                    help="Experiment directory containing params.json")
parser.add_argument('--data_dir', default='data/64x64_Amazon_Rainforest_Dataset',
                    help="Directory containing the dataset")
parser.add_argument('--restore_from', default=None,
                    help="Optional, directory or file containing weights to reload before training")


if __name__ == '__main__':
    # Set the random seed for the whole graph for reproductible experiments
    tf.set_random_seed(230)

    # Load the parameters from json file
    args = parser.parse_args()
    json_path = os.path.join(args.model_dir, 'params.json')
    assert os.path.isfile(json_path), "No json configuration file found at {}".format(json_path)
    params = Params(json_path)

    # Check that we are not overwriting some previous experiment
    # Comment these lines if you are developing your model and don't care about overwritting
    model_dir_has_best_weights = os.path.isdir(os.path.join(args.model_dir, "best_weights"))
    overwritting = model_dir_has_best_weights and args.restore_from is None
    assert not overwritting, "Weights found in model_dir, aborting to avoid overwrite"

    # Set the logger
    set_logger(os.path.join(args.model_dir, 'train.log'))

    # Create the input data pipeline
    logging.info("Creating the datasets...")
    data_dir = args.data_dir
    train_data_dir = os.path.join(data_dir, "train_Amazon_Rainforest")
    dev_data_dir = os.path.join(data_dir, "dev_Amazon_Rainforest")

    # Get the filenames and labels from the train and dev sets
    train_filenames_labels = pd.read_csv(os.path.join(data_dir, 'train_Amazon_Rainforest.csv'))
    train_filenames = [os.path.join(train_data_dir, f) + ".jpg" for f in train_filenames_labels.image_name.tolist()]

    eval_filenames_labels = pd.read_csv(os.path.join(data_dir, 'dev_Amazon_Rainforest.csv'))
    eval_filenames = [os.path.join(dev_data_dir, f) + ".jpg" for f in eval_filenames_labels.image_name.tolist()]

    # Build list with unique labels
    label_list = [[],[]]
    for i, tags in enumerate([train_filenames_labels.tags.values, eval_filenames_labels.tags.values]):
        for tag_str in tags:
            labels = tag_str.split(' ')
            for label in labels:
                if label not in label_list[i]:
                    label_list[i].append(label)
    assert(len(label_list[0]) == len(label_list[1]))

    # # Add onehot features for every label
    for label in label_list[0]:
        train_filenames_labels[label] = train_filenames_labels['tags'].apply(lambda x: 1 if label in x.split(' ') else 0)
        eval_filenames_labels[label] = eval_filenames_labels['tags'].apply(lambda x: 1 if label in x.split(' ') else 0)

    # Convert the labels to a matrix
    # Labels will be  0 or 1 for each category
    train_labels = train_filenames_labels.drop(["image_name", 'tags'], axis=1).as_matrix()
    eval_labels = eval_filenames_labels.drop(["image_name", 'tags'], axis=1).as_matrix()

    # Specify the sizes of the dataset we train on and evaluate on
    params.train_size = len(train_filenames)
    params.eval_size = len(eval_filenames)

    # Create the two iterators over the two datasets
    train_inputs = input_fn(True, train_filenames, train_labels, params)
    eval_inputs = input_fn(False, eval_filenames, eval_labels, params)

    # Define the model
    logging.info("Creating the model...")
    train_model_spec = model_fn('train', train_inputs, params)
    eval_model_spec = model_fn('eval', eval_inputs, params, reuse=True)

    # Train the model
    logging.info("Starting training for {} epoch(s)".format(params.num_epochs))
    train_and_evaluate(train_model_spec, eval_model_spec, args.model_dir, params, args.restore_from)
