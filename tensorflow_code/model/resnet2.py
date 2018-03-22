
#########################################################################
#########################################################################
# Disclaimer: This code was taken from the internet and modified for this project.
# https://github.com/tensorflow/models/tree/master/official/resnet
#########################################################################
#########################################################################


#########################################################################
# Copyright 2017 The TensorFlow Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================
"""Contains definitions for Residual Networks.

Residual networks ('v1' ResNets) were originally proposed in:
[1] Kaiming He, Xiangyu Zhang, Shaoqing Ren, Jian Sun
    Deep Residual Learning for Image Recognition. arXiv:1512.03385

The full preactivation 'v2' ResNet variant was introduced by:
[2] Kaiming He, Xiangyu Zhang, Shaoqing Ren, Jian Sun
    Identity Mappings in Deep Residual Networks. arXiv: 1603.05027

The key difference of the full preactivation 'v2' variant compared to the
'v1' variant in [1] is the use of batch normalization before every weight layer
rather than after.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function


import tensorflow as tf


_BATCH_NORM_DECAY = 0.997
_BATCH_NORM_EPSILON = 1e-5
DEFAULT_VERSION = 2


################################################################################
# Convenience functions for building the ResNet model.
################################################################################
def batch_norm(inputs, training):
    """Performs a batch normalization using a standard set of parameters."""
    # We set fused=True for a significant performance boost. See
    # https://www.tensorflow.org/performance/performance_guide#common_fused_ops
    return tf.layers.batch_normalization(
        inputs=inputs,
        momentum=_BATCH_NORM_DECAY, epsilon=_BATCH_NORM_EPSILON, center=True,
        scale=True, training=training, fused=True)


def fixed_padding(inputs, kernel_size):
    """Pads the input along the spatial dimensions independently of input size.

    Args:
      inputs: A tensor of size [batch, channels, height_in, width_in] or
        [batch, height_in, width_in, channels] depending on data_format.
      kernel_size: The kernel to be used in the conv2d or max_pool2d operation.
                   Should be a positive integer.
      data_format: The input format ('channels_last' or 'channels_first').

    Returns:
      A tensor with the same format as the input with the data either intact
      (if kernel_size == 1) or padded (if kernel_size > 1).
    """
    pad_total = kernel_size - 1
    pad_beg = pad_total // 2
    pad_end = pad_total - pad_beg

    padded_inputs = tf.pad(inputs, [[0, 0], [pad_beg, pad_end], [pad_beg, pad_end], [0, 0]])
    return padded_inputs


def conv2d_fixed_padding(inputs, filters, kernel_size, strides, weight_decay=0.001):
    """Strided 2-D convolution with explicit padding."""
    # The padding is consistent and is based only on `kernel_size`, not on the
    # dimensions of `inputs` (as opposed to using `tf.layers.conv2d` alone).

    if strides > 1:
        inputs = fixed_padding(inputs, kernel_size)
    print(inputs, filters, kernel_size, strides)
    return tf.contrib.layers.conv2d(
        inputs=inputs, num_outputs=filters, kernel_size=kernel_size, stride=strides,
        padding=('SAME' if strides == 1 else 'VALID'),
        weights_regularizer=tf.contrib.layers.l2_regularizer(weight_decay))

################################################################################
# ResNet block definitions.
################################################################################


def _building_block_v1(inputs, filters, training, projection_shortcut, strides, weight_decay=0.001):
    """
    Convolution then batch normalization then ReLU as described by:
      Deep Residual Learning for Image Recognition
      https://arxiv.org/pdf/1512.03385.pdf
      by Kaiming He, Xiangyu Zhang, Shaoqing Ren, and Jian Sun, Dec 2015.

    Args:
      inputs: A tensor of size [batch, channels, height_in, width_in] or
        [batch, height_in, width_in, channels] depending on data_format.
      filters: The number of filters for the convolutions.
      training: A Boolean for whether the model is in training or inference
        mode. Needed for batch normalization.
      projection_shortcut: The function to use for projection shortcuts
        (typically a 1x1 convolution when downsampling the input).
      strides: The block's stride. If greater than 1, this block will ultimately
        downsample the input.
      data_format: The input format ('channels_last' or 'channels_first').

    Returns:
      The output tensor of the block.
    """
    shortcut = inputs

    if projection_shortcut is not None:
        shortcut = projection_shortcut(inputs, weight_decay)
        shortcut = batch_norm(inputs=shortcut, training=training)

    inputs = conv2d_fixed_padding(
        inputs=inputs, filters=filters, kernel_size=3, strides=strides,
        weight_decay=weight_decay)
    inputs = batch_norm(inputs, training)
    inputs = tf.nn.relu(inputs)

    inputs = conv2d_fixed_padding(
        inputs=inputs, filters=filters, kernel_size=3, strides=1,
        weight_decay=weight_decay)
    inputs = batch_norm(inputs, training)
    inputs += shortcut
    inputs = tf.nn.relu(inputs)

    return inputs


def _building_block_v2(inputs, filters, training, projection_shortcut, strides, weight_decay=0.001):
    """
    Batch normalization then ReLu then convolution as described by:
      Identity Mappings in Deep Residual Networks
      https://arxiv.org/pdf/1603.05027.pdf
      by Kaiming He, Xiangyu Zhang, Shaoqing Ren, and Jian Sun, Jul 2016.

    Args:
      inputs: A tensor of size [batch, channels, height_in, width_in] or
        [batch, height_in, width_in, channels] depending on data_format.
      filters: The number of filters for the convolutions.
      training: A Boolean for whether the model is in training or inference
        mode. Needed for batch normalization.
      projection_shortcut: The function to use for projection shortcuts
        (typically a 1x1 convolution when downsampling the input).
      strides: The block's stride. If greater than 1, this block will ultimately
        downsample the input.
      data_format: The input format ('channels_last' or 'channels_first').

    Returns:
      The output tensor of the block.
    """
    shortcut = inputs
    inputs = batch_norm(inputs, training)
    inputs = tf.nn.relu(inputs)

    # The projection shortcut should come after the first batch norm and ReLU
    # since it performs a 1x1 convolution.
    if projection_shortcut is not None:
        shortcut = projection_shortcut(inputs, weight_decay)

    inputs = conv2d_fixed_padding(
        inputs=inputs, filters=filters, kernel_size=3, strides=strides,
        weight_decay=weight_decay)

    inputs = batch_norm(inputs, training)
    inputs = tf.nn.relu(inputs)
    inputs = conv2d_fixed_padding(
        inputs=inputs, filters=filters, kernel_size=3, strides=1,
        weight_decay=weight_decay)

    return inputs + shortcut


def _bottleneck_block_v1(inputs, filters, training, projection_shortcut,
                         strides, weight_decay=0.001):
    """
    Similar to _building_block_v1(), except using the "bottleneck" blocks
    described in:
      Convolution then batch normalization then ReLU as described by:
        Deep Residual Learning for Image Recognition
        https://arxiv.org/pdf/1512.03385.pdf
        by Kaiming He, Xiangyu Zhang, Shaoqing Ren, and Jian Sun, Dec 2015.
    """
    shortcut = inputs

    if projection_shortcut is not None:
        shortcut = projection_shortcut(inputs, weight_decay)
        shortcut = batch_norm(inputs=shortcut, training=training)

    inputs = conv2d_fixed_padding(
        inputs=inputs, filters=filters, kernel_size=1, strides=1,
        weight_decay=weight_decay)
    inputs = batch_norm(inputs, training)
    inputs = tf.nn.relu(inputs)

    inputs = conv2d_fixed_padding(
        inputs=inputs, filters=filters, kernel_size=3, strides=strides,
        weight_decay=weight_decay)
    inputs = batch_norm(inputs, training)
    inputs = tf.nn.relu(inputs)

    inputs = conv2d_fixed_padding(
        inputs=inputs, filters=4 * filters, kernel_size=1, strides=1,
        weight_decay=weight_decay)
    inputs = batch_norm(inputs, training)
    inputs += shortcut
    inputs = tf.nn.relu(inputs)

    return inputs


def _bottleneck_block_v2(inputs, filters, training, projection_shortcut,
                         strides, weight_decay=0.001):
    """
    Similar to _building_block_v2(), except using the "bottleneck" blocks
    described in:
      Convolution then batch normalization then ReLU as described by:
        Deep Residual Learning for Image Recognition
        https://arxiv.org/pdf/1512.03385.pdf
        by Kaiming He, Xiangyu Zhang, Shaoqing Ren, and Jian Sun, Dec 2015.

    adapted to the ordering conventions of:
      Batch normalization then ReLu then convolution as described by:
        Identity Mappings in Deep Residual Networks
        https://arxiv.org/pdf/1603.05027.pdf
        by Kaiming He, Xiangyu Zhang, Shaoqing Ren, and Jian Sun, Jul 2016.
    """
    shortcut = inputs
    inputs = batch_norm(inputs, training)
    inputs = tf.nn.relu(inputs)

    # The projection shortcut should come after the first batch norm and ReLU
    # since it performs a 1x1 convolution.
    if projection_shortcut is not None:
        shortcut = projection_shortcut(inputs, weight_decay)

    inputs = conv2d_fixed_padding(
        inputs=inputs, filters=filters, kernel_size=1, strides=1,
        weight_decay=weight_decay)

    inputs = batch_norm(inputs, training)
    inputs = tf.nn.relu(inputs)
    inputs = conv2d_fixed_padding(
        inputs=inputs, filters=filters, kernel_size=3, strides=strides,
        weight_decay=weight_decay)

    inputs = batch_norm(inputs, training)
    inputs = tf.nn.relu(inputs)
    inputs = conv2d_fixed_padding(
        inputs=inputs, filters=4 * filters, kernel_size=1, strides=1,
        weight_decay=weight_decay)

    return inputs + shortcut


def block_layer(inputs, filters, bottleneck, block_fn, blocks, strides,
                training, name, weight_decay=0.001):
    """Creates one layer of blocks for the ResNet model.

    Args:
      inputs: A tensor of size [batch, channels, height_in, width_in] or
        [batch, height_in, width_in, channels] depending on data_format.
      filters: The number of filters for the first convolution of the layer.
      bottleneck: Is the block created a bottleneck block.
      block_fn: The block to use within the model, either `building_block` or
        `bottleneck_block`.
      blocks: The number of blocks contained in the layer.
      strides: The stride to use for the first convolution of the layer. If
        greater than 1, this layer will ultimately downsample the input.
      training: Either True or False, whether we are currently training the
        model. Needed for batch norm.
      name: A string name for the tensor output of the block layer.
      data_format: The input format ('channels_last' or 'channels_first').

    Returns:
      The output tensor of the block layer.
    """

    # Bottleneck blocks end with 4x the number of filters as they start with
    filters_out = filters * 4 if bottleneck else filters

    def projection_shortcut(inputs, weight_decay=0.001):
        return conv2d_fixed_padding(
            inputs=inputs, filters=filters_out, kernel_size=1, strides=strides,
            weight_decay=weight_decay)

    # Only the first block per block_layer uses projection_shortcut and strides
    inputs = block_fn(inputs, filters, training, projection_shortcut, strides, weight_decay)

    for _ in range(1, blocks):
        inputs = block_fn(inputs, filters, training, None, 1, weight_decay)

    return tf.identity(inputs, name)


class Model(object):
    """Base class for building the Resnet Model.
    """

    def __init__(self, bottleneck, num_classes, num_filters,
                 kernel_size,
                 conv_stride, first_pool_size, first_pool_stride,
                 second_pool_size, second_pool_stride, block_sizes, block_strides,
                 final_size, version=DEFAULT_VERSION, weight_decay=0.001):
        """Creates a model for classifying an image.

        Args:
          resnet_size: A single integer for the size of the ResNet model.
          bottleneck: Use regular blocks or bottleneck blocks.
          num_classes: The number of classes used as labels.
          num_filters: The number of filters to use for the first block layer
            of the model. This number is then doubled for each subsequent block
            layer.
          kernel_size: The kernel size to use for convolution.
          conv_stride: stride size for the initial convolutional layer
          first_pool_size: Pool size to be used for the first pooling layer.
            If none, the first pooling layer is skipped.
          first_pool_stride: stride size for the first pooling layer. Not used
            if first_pool_size is None.
          second_pool_size: Pool size to be used for the second pooling layer.
          second_pool_stride: stride size for the final pooling layer
          block_sizes: A list containing n values, where n is the number of sets of
            block layers desired. Each value should be the number of blocks in the
            i-th set.
          block_strides: List of integers representing the desired stride size for
            each of the sets of block layers. Should be same length as block_sizes.
          final_size: The expected size of the model after the second pooling.
          version: Integer representing which version of the ResNet network to use.
            See README for details. Valid values: [1, 2]
          data_format: Input format ('channels_last', 'channels_first', or None).
            If set to None, the format is dependent on whether a GPU is available.
        """
        self.resnet_version = version
        if version not in (1, 2):
            raise ValueError("Resnet version should be 1 or 2. See README for citations.")

        self.bottleneck = bottleneck
        if bottleneck:
            if version == 1:
                self.block_fn = _bottleneck_block_v1
            else:
                self.block_fn = _bottleneck_block_v2
        else:
            if version == 1:
                self.block_fn = _building_block_v1
            else:
                self.block_fn = _building_block_v2

        self.num_classes = num_classes
        self.num_filters = num_filters
        self.kernel_size = kernel_size
        self.conv_stride = conv_stride
        self.first_pool_size = first_pool_size
        self.first_pool_stride = first_pool_stride
        self.second_pool_size = second_pool_size
        self.second_pool_stride = second_pool_stride
        self.block_sizes = block_sizes
        self.block_strides = block_strides
        self.final_size = final_size
        self.weight_decay = weight_decay

    def __call__(self, inputs, training):
        """Add operations to classify a batch of input images.

        Args:
          inputs: A Tensor representing a batch of input images.
          training: A boolean. Set to True to add operations required only when
            training the classifier.

        Returns:
          A logits Tensor with shape [<batch_size>, self.num_classes].
        """

        inputs = conv2d_fixed_padding(
            inputs=inputs, filters=self.num_filters, kernel_size=self.kernel_size,
            strides=self.conv_stride, weight_decay=self.weight_decay)
        inputs = tf.identity(inputs, 'initial_conv')

        if self.first_pool_size:
            inputs = tf.layers.max_pooling2d(
                inputs=inputs, pool_size=self.first_pool_size,
                strides=self.first_pool_stride, padding='SAME')
            inputs = tf.identity(inputs, 'initial_max_pool')

        for i, num_blocks in enumerate(self.block_sizes):
            num_filters = self.num_filters * (2**i)
            inputs = block_layer(
                inputs=inputs, filters=num_filters, bottleneck=self.bottleneck,
                block_fn=self.block_fn, blocks=num_blocks,
                strides=self.block_strides[i], training=training,
                name='block_layer{}'.format(i + 1), weight_decay=self.weight_decay)

        inputs = batch_norm(inputs, training)
        inputs = tf.nn.relu(inputs)
        inputs = tf.layers.average_pooling2d(
            inputs=inputs, pool_size=self.second_pool_size,
            strides=self.second_pool_stride, padding='VALID')
        inputs = tf.identity(inputs, 'final_avg_pool')

        inputs = tf.contrib.layers.flatten(inputs)
        inputs = tf.contrib.layers.fully_connected(inputs=inputs,
                                                   num_outputs=self.num_classes,
                                                   weights_regularizer=tf.contrib.layers.l2_regularizer(self.weight_decay))
        inputs = tf.identity(inputs, 'final_dense')
        return inputs


def build_resnet_(is_training, inputs, params):
    resnet = Model(params.bottleneck, params.num_classes, params.num_filters,
                   params.kernel_size,
                   params.conv_stride, params.first_pool_size, params.first_pool_stride,
                   params.second_pool_size, params.second_pool_stride, params.block_sizes, params.block_strides,
                   params.num_classes, version=DEFAULT_VERSION, weight_decay=params.weight_decay)
    images = inputs['images']
    assert images.get_shape().as_list() == [None, params.image_size, params.image_size, 3]
    out = images
    return resnet.__call__(out, is_training)
