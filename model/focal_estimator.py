from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import numpy as np
import tensorflow as tf  # pylint: disable=g-bad-import-order
from tensorflow.contrib.learn import ModeKeys


_EPSILON = 1e-10


# Focal loss.
def focal_loss(one_hot_labels, logits, alpha, gamma=2.):
    assert one_hot_labels.get_shape()[1] == len(alpha), "The length of alpha doesn't match the size of one hot lables."
    probs = tf.clip_by_value(tf.nn.sigmoid(logits), _EPSILON, 1.-_EPSILON)
    alphas = tf.convert_to_tensor(alpha)
    pos_ce = -tf.multiply(one_hot_labels, tf.log(probs))
    neg_ce = -tf.multiply(1 - one_hot_labels, tf.log(1 - probs + _EPSILON))
    xentropy = pos_ce + neg_ce
    focal = tf.multiply(tf.pow(1 - probs, gamma), xentropy)
    alpha_focal = tf.multiply(alphas, focal)
    return tf.reduce_mean(alpha_focal)


def build(model_dir, params={}, run_config=None):
  """Build an estimator appropriate for the given model type."""

  def model_fn(features, labels, mode, params):

    # wide model
    wide = tf.feature_column.input_layer(features, params["wide_columns"])

    # deep model
    deep = tf.feature_column.input_layer(features, params["deep_columns"])
    for num_unit in params["hidden_units"]:
        deep = tf.layers.dense(deep, num_unit, tf.nn.relu, kernel_initializer=tf.contrib.layers.xavier_initializer())
        deep = tf.layers.dropout(deep, params["dropout_rate"], training=mode == ModeKeys.TRAIN)

    # wide + deep
    wide_deep = tf.concat([wide, deep], 1)
    logits = tf.layers.dense(wide_deep, params["n_class"])
    arg_maxes = tf.argmax(logits, axis=1)

    # For calculating ndcg, set the prediction like score.
    probs = tf.clip_by_value(tf.nn.softmax(logits), _EPSILON, 1.-_EPSILON)
    prob_maxes = tf.reduce_max(probs, axis=1)
    predictions = tf.cast(arg_maxes, tf.float32) + prob_maxes

    loss = None
    train_op = None
    eval_metric_ops = {}
    if mode != ModeKeys.INFER:
        # Transform labels from [1,2,3,4] to [0,1,2,3]
        labels = labels - 1

        one_hot_labels = tf.one_hot(tf.cast(labels, tf.int32), params["n_class"])
        loss = focal_loss(one_hot_labels, logits, params["alpha"], params["gamma"])
        optimizer = tf.train.ProximalAdagradOptimizer(params["learning_rate"], l1_regularization_strength=0.001)
        train_op = optimizer.minimize(loss, tf.train.get_global_step())
        eval_metric_ops = { "accuracy": tf.metrics.accuracy(tf.cast(labels, tf.int32), arg_maxes) }

    return tf.estimator.EstimatorSpec(mode, predictions, loss, train_op, eval_metric_ops)
  return tf.estimator.Estimator(model_fn, model_dir, run_config, params)



