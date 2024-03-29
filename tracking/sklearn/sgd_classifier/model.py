import argparse
import numpy as np

# Polyaxon
from polyaxon.tracking import Run

from sklearn import datasets
from sklearn.linear_model import SGDClassifier
from sklearn.model_selection import cross_val_score


def load_data():
    iris = datasets.load_iris()
    return iris.data, iris.target


def model(X, y, loss, penalty, l1_ratio, max_iter, tol):
    classifier = SGDClassifier(
        loss=loss,
        penalty=penalty,
        l1_ratio=l1_ratio,
        max_iter=max_iter,
        tol=tol,
    )
    return cross_val_score(classifier, X, y, cv=5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--loss',
        type=str,
        default='log')
    parser.add_argument(
        '--penalty',
        type=str,
        default='elasticnet')
    parser.add_argument(
        '--l1_ratio',
        type=float,
        default=1.0)
    parser.add_argument(
        '--max_iter',
        type=int,
        default=1000)
    parser.add_argument(
        '--tol',
        type=float,
        default=0.001
    )
    args = parser.parse_args()

    # Polyaxon
    experiment = Run(project='sgd-classifier', tags=['examples', 'scikit-learn'], is_new=True)
    experiment.log_inputs(loss=args.loss,
                          penalty=args.penalty,
                          l1_ratio=args.l1_ratio,
                          max_iter=args.max_iter,
                          tol=args.tol)

    (X, y) = load_data()

    # Polyaxon
    experiment.log_data_ref(content=X, name='dataset_X')
    experiment.log_data_ref(content=y, name='dataset_y')

    accuracies = model(X=X,
                       y=y,
                       loss=args.loss,
                       penalty=args.penalty,
                       l1_ratio=args.l1_ratio,
                       max_iter=args.max_iter,
                       tol=args.tol)
    accuracy_mean, accuracy_std = (np.mean(accuracies), np.std(accuracies))
    print('Accuracy: {} +/- {}'.format(accuracy_mean, accuracy_std))

    # Polyaxon
    experiment.log_outputs(accuracy_mean=accuracy_mean, accuracy_std=accuracy_std)
