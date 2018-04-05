# -*- coding: utf-8 -*-
"""Learning rates comparison - CNN

Automatically generated by Colaboratory.

Original file is located at
		https://colab.research.google.com/drive/1ynqfIQK9HgbAHqaED6mBxAVEP2MMsHhb
"""

#	 Copyright 2016 The TensorFlow Authors. All Rights Reserved.
#
#	 Licensed under the Apache License, Version 2.0 (the "License");
#	 you may not use this file except in compliance with the License.
#	 You may obtain a copy of the License at
#
#		http://www.apache.org/licenses/LICENSE-2.0
#
#	 Unless required by applicable law or agreed to in writing, software
#	 distributed under the License is distributed on an "AS IS" BASIS,
#	 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#	 See the License for the specific language governing permissions and
#	 limitations under the License.
"""Convolutional Neural Network Estimator for MNIST, built with tf.layers."""

import time
from datetime import datetime
import traceback
import uuid
import shutil
import os
import argparse

import numpy as np
import tensorflow as tf

from ploty import Ploty
from hooks import *



class Model(object):

		def __init__(self, 
			optimizer_fn=None, 
			val_target=0.99, 
			max_secs=100, 
			scale=1, 
			output_path="/tmp/", 
			train_callback=None,
			eval_callback=None, 
			train_end_callback=None,
			check_stopping_every=50):
				
				self.optimizer_fn = optimizer_fn
				self.val_target = val_target
				self.max_secs = max_secs
				self.scale = scale
				self.output_path = output_path
				self.train_callback = train_callback
				self.train_end_callback = train_end_callback
				self.eval_callback = eval_callback
				self.check_stopping_every = check_stopping_every
				self.early_stop = True

				self.start_time = time.time()

				# Load training and eval data
				mnist = tf.contrib.learn.datasets.load_dataset("mnist")
				train_data = mnist.train.images # Returns np.array
				train_labels = np.asarray(mnist.train.labels, dtype=np.int32)
				eval_data = mnist.test.images	 # Returns np.array
				eval_labels = np.asarray(mnist.test.labels, dtype=np.int32)

				# Data input functions
				self.train_input_fn = tf.estimator.inputs.numpy_input_fn(
						x={"x": train_data},
						y=train_labels,
						batch_size=100,
						num_epochs=None,
						shuffle=True)

				self.eval_input_fn = tf.estimator.inputs.numpy_input_fn(
						x={"x": eval_data},
						y=eval_labels,
						num_epochs=1,
						shuffle=False)

				 # Create a model
				# This lambda hack removes the self reference
				self.model_fn = lambda features, labels, mode: self.model_fn_bare(features, labels, mode)



		def model_fn_bare(self, features, labels, mode):
				"""Model function for CNN."""
				
				# Input Layer
				# Reshape X to 4-D tensor: [batch_size, width, height, channels]
				# MNIST images are 28x28 pixels, and have one color channel
				input_layer = tf.reshape(features["x"], [-1, 28, 28, 1])

				# Convolutional Layer #1
				# Computes 32 features using a 5x5 filter with ReLU activation.
				# Padding is added to preserve width and height.
				# Input Tensor Shape: [batch_size, 28, 28, 1]
				# Output Tensor Shape: [batch_size, 28, 28, 32]
				conv1 = tf.layers.conv2d(
						inputs=input_layer,
						filters=round(32*self.scale),
						kernel_size=[5, 5],
						padding="same",
						activation=tf.nn.relu)

				# Pooling Layer #1
				# First max pooling layer with a 2x2 filter and stride of 2
				# Input Tensor Shape: [batch_size, 28, 28, 32]
				# Output Tensor Shape: [batch_size, 14, 14, 32]
				pool1 = tf.layers.max_pooling2d(inputs=conv1, pool_size=[2, 2], strides=2)

				# Convolutional Layer #2
				# Computes 64 features using a 5x5 filter.
				# Padding is added to preserve width and height.
				# Input Tensor Shape: [batch_size, 14, 14, 32]
				# Output Tensor Shape: [batch_size, 14, 14, 64]
				conv2 = tf.layers.conv2d(
						inputs=pool1,
						filters=round(64 * self.scale),
						kernel_size=[5, 5],
						padding="same",
						activation=tf.nn.relu)

				# Pooling Layer #2
				# Second max pooling layer with a 2x2 filter and stride of 2
				# Input Tensor Shape: [batch_size, 14, 14, 64]
				# Output Tensor Shape: [batch_size, 7, 7, 64]
				pool2 = tf.layers.max_pooling2d(inputs=conv2, pool_size=[2, 2], strides=2)

				# Flatten tensor into a batch of vectors
				# Input Tensor Shape: [batch_size, 7, 7, 64]
				# Output Tensor Shape: [batch_size, 7 * 7 * 64]
				pool2_flat = tf.reshape(pool2, [-1, 7 * 7 * round(self.scale* 64)])

				# Dense Layer
				# Densely connected layer with 1024 neurons
				# Input Tensor Shape: [batch_size, 7 * 7 * 64]
				# Output Tensor Shape: [batch_size, 1024]
				dense = tf.layers.dense(inputs=pool2_flat, units=round(1024*self.scale), activation=tf.nn.relu)

				# Add dropout operation; 0.6 probability that element will be kept
				dropout = tf.layers.dropout(
						inputs=dense, rate=0.4, training=mode == tf.estimator.ModeKeys.TRAIN)

				# Logits layer
				# Input Tensor Shape: [batch_size, 1024]
				# Output Tensor Shape: [batch_size, 10]
				logits = tf.layers.dense(inputs=dropout, units=10)

				predictions = {
						# Generate predictions (for PREDICT and EVAL mode)
						"classes": tf.argmax(input=logits, axis=1),
						# Add `softmax_tensor` to the graph. It is used for PREDICT and by the
						# `logging_hook`.
						"probabilities": tf.nn.softmax(logits, name="softmax_tensor")
				}

				# Add evaluation metrics (for EVAL mode)
				eval_metric_ops = {
					"accuracy": tf.metrics.accuracy(
							labels=labels, predictions=predictions["classes"])
				}


				# Hooks
				train_hooks = []
				eval_hooks = []

				early_stop = EarlyStopping(
					eval_metric_ops["accuracy"], 
					start_time=self.start_time,
					target=self.val_target, 
					check_every=self.check_stopping_every,
					max_secs=self.max_secs)

				if self.early_stop:
					train_hooks.append(early_stop)

				if self.train_end_callback is not None:
					m = LastMetricHook(eval_metric_ops["accuracy"], self.train_end_callback)
					train_hooks.append(m)

				if self.train_callback is not None:
					m = MetricHook(eval_metric_ops["accuracy"], self.train_callback)
					train_hooks.append(m)

				if self.eval_callback is not None:
					m = MetricHook(eval_metric_ops["accuracy"], self.eval_callback)
					eval_hooks.append(m)

				### Create EstimatorSpecs ###

				if mode == tf.estimator.ModeKeys.PREDICT:
						return tf.estimator.EstimatorSpec(mode=mode, predictions=predictions)

				# Calculate Loss (for both TRAIN and EVAL modes)
				loss = tf.losses.sparse_softmax_cross_entropy(labels=labels, logits=logits)

				# Configure the Training Op (for TRAIN mode)
				if mode == tf.estimator.ModeKeys.TRAIN:
					global_step = tf.train.get_global_step()
					self.optimizer = self.optimizer_fn(global_step)
					train_op = self.optimizer.minimize(
							loss=loss,
							global_step=global_step)

					return tf.estimator.EstimatorSpec(
						mode=mode, 
						loss=loss,
						train_op=train_op,
						training_hooks=train_hooks)

				if mode == tf.estimator.ModeKeys.EVAL:
					return tf.estimator.EstimatorSpec(
						mode=mode, 
						loss=loss, 
						eval_metric_ops=eval_metric_ops, 
						evaluation_hooks=eval_hooks)

		def generate_config(self):
			# Create the Estimator
			model_dir = self.output_path + str(uuid.uuid1())

			config = tf.estimator.RunConfig(
				model_dir=model_dir,
				tf_random_seed=3141592
			)

			return config

		def post_run(self, config):

			try:
				shutil.rmtree(config.model_dir)
			except:
				pass


		def train_and_evaluate(self, max_steps, eval_throttle_secs):
				
			config = self.generate_config()

			mnist_classifier = tf.estimator.Estimator(
					model_fn=self.model_fn, config=config)

			# Specs for train and eval
			train_spec = tf.estimator.TrainSpec(input_fn=self.train_input_fn, max_steps=max_steps)
			eval_spec = tf.estimator.EvalSpec(input_fn=self.eval_input_fn, throttle_secs=eval_throttle_secs)

			tf.estimator.train_and_evaluate(mnist_classifier, train_spec, eval_spec)

			self.post_run(config)

		def train(self, steps=None, max_steps=None):
			
			config = self.generate_config()

			mnist_classifier = tf.estimator.Estimator(
				model_fn=self.model_fn, config=config)

			r = mnist_classifier.train(self.train_input_fn, steps=steps, max_steps=max_steps)

			self.post_run(config)

			return r




### Static data ###

output_path = "/tmp/"

optimizers = {
		"Adam": tf.train.AdamOptimizer,
		"Adagrad": tf.train.AdagradOptimizer,
		"Momentum": lambda lr: tf.train.MomentumOptimizer(lr, 0.5),
		"GD": tf.train.GradientDescentOptimizer,
		"Adadelta": tf.train.AdadeltaOptimizer,
		"RMSProp": tf.train.RMSPropOptimizer,	
}

ideal_lr = {
	"Adam": 0.00146,
	"Adagrad": 0.1,
	"Momentum": 0.215,
	"GD": 0.215,
	"Adadelta": 3.16,
	"RMSProp": 0.00146,	
}

schedules = [
#	 "exp_decay", 
	"fixed", 
#	 "cosine_restart"
]




### Learning rates ###
			
def LRRange(mul=5):
	
	for i in range(mul*6, 0, -1):
		lr = pow(0.1, i/mul)
		yield lr

	for i in range(1, 2*mul+1):
		lr = pow(10, i/mul)
		yield lr


def LRRangeAdam():
	yield ideal_lr["Adam"]
	for i in range(1, 5):
		lr = pow(0.1, i)
		yield lr
		
		
def lr_schedule(optimizer, starter_learning_rate=0.1, 
								global_step=None, mode="fixed", 
								decay_rate=0.96, decay_steps=100, 
								cycle_lr_decay=0.001, cycle_length=1000):
	
	if mode == "fixed":
		return optimizer(starter_learning_rate)
	
	elif mode == "exp_decay":
		lr = tf.train.exponential_decay(starter_learning_rate, global_step,
																		decay_steps, decay_rate, staircase=True)
		return optimizer(lr)
	
	elif mode == "cosine_restart":
		lr = tf.train.cosine_decay_restarts(
			starter_learning_rate,
			global_step,
			cycle_length,
			alpha=cycle_lr_decay)
		
		return optimizer(lr)
	
	elif mode == "triangle":
	
		min_lr = starter_learning_rate * cycle_lr_decay
	
		cycle = tf.floor(1+global_step/(2*cycle_length))
		x = tf.abs(global_step/cycle_length - 2*cycle + 1)
		lr = starter_learning_rate + (starter_learning_rate-min_lr)*tf.maximum(0, (1-x))/float(2**(cycle-1))





def build_model(
	FLAGS,
	max_secs,
	optimizer="Adam", 
	schedule="fixed", 
	lr=0.01, 
	scale=1,
	train_callback=None, 
	eval_callback=None,
	train_end_callback=None,
	stop_after_acc=0.97):

		print(f"Starting run {optimizer}({lr}) scale={scale}")

		opt = optimizers[optimizer]

		def get_optimizer(global_step):
				return lr_schedule(opt, lr, global_step=global_step, mode=schedule)

		m = Model(
			optimizer_fn=get_optimizer, 
			val_target=stop_after_acc, 
			max_secs=max_secs, 
			scale=scale,
			train_callback=train_callback,
			eval_callback=eval_callback,
			train_end_callback=train_end_callback,
			check_stopping_every=50)

		return m


def plt_time_vs_lr(FLAGS):
		p = Ploty(output_path=FLAGS.output_dir, title="Time to train vs learning rate", x="Learning rate",log_x=True, log_y=True)
		for opt in optimizers.keys():
			for sched in schedules:
				for lr in LRRange(6):
					try:
						print(f"Running {opt} {sched} {lr}")

						def cb(r):
							p.add_result(lr, r["time_taken"], opt + " " + sched, data=r)

						r = run(opt, sched, lr, scale=FLAGS.scale, max_secs=FLAGS.max_secs, eval_callback=cb)

					except Exception:
						traceback.print_exc()
						pass

			try:
				p.copy_to_drive()	
			except Exception:
				tf.logging.error(e)
				pass

def plt_time_vs_model_size(FLAGS):

		oversample = FLAGS.oversample

		stop_after_acc = 0.96
		
		p = Ploty(output_path=FLAGS.output_dir,title="Time to train vs size of model",x="Model scale",clear_screen=True)
		for opt in ["Adam"]:
			for sched in schedules:
				for lr in LRRangeAdam():
					for i in range(1*oversample, 10*oversample):
						scale = i/oversample

						try:

							d = {}
							
							def cb(acc):
								taken = time.time() - d["time_start"]
								if acc >= stop_after_acc:
									p.add_result(scale, taken, opt+"("+str(lr)+")", extra_data={"acc":acc, "lr": lr, "opt": opt, "scale":scale, "time":taken})
								else:
									tf.logging.error("Failed to train.")

							m = build_model(
								FLAGS,
								max_secs=60*4,
								optimizer=opt, 
								schedule=sched, 
								lr=lr, 
								scale=scale,
								train_end_callback=cb,
								stop_after_acc=stop_after_acc
							)

							d["time_start"] = time.time()
							m.train()

						except Exception:
							traceback.print_exc()
							pass
					
			try:
				p.copy_to_drive()	
			except:
				pass



def plt_train_trace(FLAGS):
		p = Ploty(
			output_path=FLAGS.output_dir, 
			title="Validation accuracy over time", 
			x="Time",
			y="Validation accuracy",
			log_x=True, 
			log_y=True,
			legend=True)

		sched = "fixed"
		
		for opt in optimizers.keys():

			lr = ideal_lr[opt]

			try:
				tf.logging.info(f"Running {opt} {sched} {lr}")

				time_start = time.time()

				def cb(mode):
					def d(acc):
						taken = time.time() - time_start
						p.add_result(taken, acc, opt+"-"+mode)
					return d

				m = build_model(FLAGS, 
					max_steps=70,
					optimizer=opt, 
					schedule=sched, 
					lr=lr, 
					scale=FLAGS.scale, 
					train_callback=cb("train"), 
					eval_callback=cb("eval"),
					eval_throttle_secs=3)

				m.train_and_evaluate(max_steps=70, eval_throttle_secs=3)
				
			 
			except Exception:
				traceback.print_exc()
				pass


if __name__ == "__main__":

	tf.logging.set_verbosity('INFO')

	tasks = {
		"trace": plt_train_trace,
		"time_vs_lr": plt_time_vs_lr,
		"time_vs_size": plt_time_vs_model_size
	}

	parser = argparse.ArgumentParser()
	parser.add_argument('--max-secs',				type=float, default=120)
	parser.add_argument('--scale',					type=int, default=3)
	parser.add_argument('--oversample',			type=int, default=4)
	parser.add_argument('--task',						type=str, choices=tasks.keys(),required=True)
	parser.add_argument('--output-dir',			type=str, default="./output")

	FLAGS = parser.parse_args()

	tf.logging.info("starting...")
	tasks[FLAGS.task](FLAGS)

