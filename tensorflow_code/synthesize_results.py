"""Aggregates results from the metrics_eval_best_weights.json in a parent folder."""

import argparse
import json
import os

from tabulate import tabulate
import pandas as pd

parser = argparse.ArgumentParser()
parser.add_argument('--parent_dir', default='experiments/base_model',
                    help='Directory containing results of experiments')


def aggregate_metrics(parent_dir, metrics):
    """
    Aggregate the metrics of all experiments in folder `parent_dir`.

    Assumes that `parent_dir` contains multiple experiments, with their results stored in
    `parent_dir/subdir/metrics_dev.json`

    Args:
        parent_dir: (string) path to directory containing experiments results
        metrics: (dict) subdir -> {'accuracy': ..., ...}
    """
    # Get the metrics for the folder if it has results from an experiment
    metrics_file = os.path.join(parent_dir, 'metrics_eval_best_weights.json')
    if os.path.isfile(metrics_file):
        with open(metrics_file, 'r') as f:
            metrics[parent_dir] = json.load(f)

    # Check every subdirectory of parent_dir
    for subdir in os.listdir(parent_dir):
        if not os.path.isdir(os.path.join(parent_dir, subdir)):
            continue
        else:
            aggregate_metrics(os.path.join(parent_dir, subdir), metrics)


def metrics_to_table(metrics):
    # Calculate the F2 score and create the metrics table.

    for metric in list(metrics.keys()):
        precision = metrics[metric]["precision"]
        recall = metrics[metric]["recall"]
        F2_metric = 5*precision*recall/(4*precision + recall)
        metrics[metric]["F2"] = F2_metric

    headers = metrics[list(metrics.keys())[0]].keys()
    table = [[subdir] + [values[h] for h in headers] for subdir, values in metrics.items()]
    res = tabulate(table, headers, tablefmt='pipe')
    latex_headers = ["Experiment"]+list(headers)
    latex_headers = [r"\textbf{" + header + "}" for header in latex_headers]
    df = pd.DataFrame.from_records(table, columns=latex_headers).round(3)
    print(df.to_latex(bold_rows=True, column_format= '| l | l | c | c | c | c | c |', escape=False))
    return res


if __name__ == "__main__":
    args = parser.parse_args()

    # Aggregate metrics from args.parent_dir directory
    metrics = dict()
    aggregate_metrics(args.parent_dir, metrics)
    table = metrics_to_table(metrics)

    # Display the table to terminal
    print(table)

    # Save results in parent_dir/results.md
    save_file = os.path.join(args.parent_dir, "results.md")
    with open(save_file, 'w') as f:
        f.write(table)
