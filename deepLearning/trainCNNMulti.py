import os
import json
import time
import datetime
import deepLearning.data_helpersMulti as data_helpers
import numpy as np
import tensorflow as tf
from deepLearning.CNN import TextCNN
from tensorflow.contrib import learn
from sklearn.model_selection import train_test_split

# Parameters
# ==================================================

# Data loading params
tf.flags.DEFINE_float("dev_sample_percentage", .1, "Percentage of the training data to use for validation")
tf.flags.DEFINE_string("data_file", "train_data_multi.json", "Data source for the training set.")

# Model Hyperparameters
tf.flags.DEFINE_integer("embedding_dim", 256, "Dimensionality of character embedding")
tf.flags.DEFINE_string("filter_sizes", "3,4,5", "Comma-separated filter sizes")
tf.flags.DEFINE_integer("num_filters", 256, "Number of filters per filter size")
tf.flags.DEFINE_float("dropout_keep_prob", 0.75, "Dropout keep probability")
tf.flags.DEFINE_float("l2_reg_lambda", 0.0, "L2 regularization lambda")

# Training parameters
tf.flags.DEFINE_integer("batch_size", 16, "Batch Size")
tf.flags.DEFINE_integer("num_epochs", 5, "Number of training epochs")
tf.flags.DEFINE_integer("evaluate_every", 100, "Evaluate model on dev set after this many steps")
tf.flags.DEFINE_integer("display_every", 10, "Number of iterations to display training info.")
tf.flags.DEFINE_integer("checkpoint_every", 100, "Save model after this many steps")
tf.flags.DEFINE_integer("num_checkpoints", 5, "Number of checkpoints to store")

# Misc Parameters
tf.flags.DEFINE_boolean("allow_soft_placement", True, "Allow device soft device placement")
tf.flags.DEFINE_boolean("log_device_placement", False, "Log placement of ops on devices")

FLAGS = tf.flags.FLAGS

def train_cnn_multi():
	# Data Preparation
	# ==================================================

	x_raw, y_raw, df, labels = data_helpers.load_data_and_labels(FLAGS.data_file)

	max_document_length = max([len(x.split(' ')) for x in x_raw])
	vocab_processor = learn.preprocessing.VocabularyProcessor(max_document_length)
	x = np.array(list(vocab_processor.fit_transform(x_raw)))
	y = np.array(y_raw)

	x_, x_test, y_, y_test = train_test_split(x, y, test_size=0.1, random_state=42)

	shuffle_indices = np.random.permutation(np.arange(len(y_)))
	x_shuffled = x_[shuffle_indices]
	y_shuffled = y_[shuffle_indices]
	x_train, x_dev, y_train, y_dev = train_test_split(x_shuffled, y_shuffled, test_size=0.1)

	with open('./labels.json', 'w') as outfile:
		json.dump(labels, outfile, indent=4)

	# Training
	# ==================================================

	graph = tf.Graph()
	with graph.as_default():
		session_conf = tf.ConfigProto(
			allow_soft_placement=FLAGS.allow_soft_placement,
			log_device_placement=FLAGS.log_device_placement)
		sess = tf.Session(config=session_conf)
		with sess.as_default():
			cnn = TextCNN(
				sequence_length=x_train.shape[1],
				num_classes=y_train.shape[1],
				vocab_size=len(vocab_processor.vocabulary_),
				embedding_size=FLAGS.embedding_dim,
				filter_sizes=list(map(int, FLAGS.filter_sizes.split(","))),
				num_filters=FLAGS.num_filters,
				l2_reg_lambda=FLAGS.l2_reg_lambda)

			global_step = tf.Variable(0, name="global_step", trainable=False)
			optimizer = tf.train.AdamOptimizer(1e-3)
			grads_and_vars = optimizer.compute_gradients(cnn.loss)
			train_op = optimizer.apply_gradients(grads_and_vars, global_step=global_step)

			timestamp = str(int(time.time()))
			out_dir = os.path.abspath(os.path.join(os.path.curdir, "runs", timestamp))

			checkpoint_dir = os.path.abspath(os.path.join(out_dir, "checkpoints"))
			checkpoint_prefix = os.path.join(checkpoint_dir, "model")
			if not os.path.exists(checkpoint_dir):
				os.makedirs(checkpoint_dir)
			saver = tf.train.Saver()

			# One training step: train the model with one batch
			def train_step(x_batch, y_batch):
				feed_dict = {
					cnn.input_x: x_batch,
					cnn.input_y: y_batch,
					cnn.dropout_keep_prob: FLAGS.dropout_keep_prob}
				_, step, loss, acc = sess.run([train_op, global_step, cnn.loss, cnn.accuracy], feed_dict)

			# One evaluation step: evaluate the model with one batch
			def dev_step(x_batch, y_batch):
				feed_dict = {cnn.input_x: x_batch, cnn.input_y: y_batch, cnn.dropout_keep_prob: 1.0}
				step, loss, acc, num_correct = sess.run([global_step, cnn.loss, cnn.accuracy, cnn.num_correct], feed_dict)
				return num_correct

			# Save the word_to_id map since predict.py needs it
			vocab_processor.save(os.path.join(out_dir, "text_vocab"))
			sess.run(tf.global_variables_initializer())

			# Training starts here
			train_batches = data_helpers.batch_iter(list(zip(x_train, y_train)), FLAGS.batch_size, FLAGS.num_epochs)

			for train_batch in train_batches:
				x_train_batch, y_train_batch = zip(*train_batch)
				train_step(x_train_batch, y_train_batch)
				current_step = tf.train.global_step(sess, global_step)
				feed_dict = {
					cnn.input_x: x_train_batch,
					cnn.input_y: y_train_batch,
					cnn.dropout_keep_prob: 1.0
				}
				step, loss, accuracy = sess.run(
					[global_step, cnn.loss, cnn.accuracy],
					feed_dict)
				time_str = datetime.datetime.now().isoformat()
				if current_step % FLAGS.display_every == 0:
					print("{}: step {}, loss {:g}, acc {:g}".format(time_str, step, loss, accuracy))

				if current_step % FLAGS.evaluate_every == 0:
					dev_batches = data_helpers.batch_iter(list(zip(x_dev, y_dev)), FLAGS.batch_size, 1)
					total_dev_correct = 0
					for dev_batch in dev_batches:
						x_dev_batch, y_dev_batch = zip(*dev_batch)
						num_dev_correct = dev_step(x_dev_batch, y_dev_batch)
						total_dev_correct += num_dev_correct

					print("{}: step {}, loss {:g}, acc {:g}".format(time_str, step, loss, accuracy))

				if current_step % FLAGS.checkpoint_every == 0:
					path = saver.save(sess, checkpoint_prefix, global_step=current_step)
					print("Saved model checkpoint to {}\n".format(path))

			test_batches = data_helpers.batch_iter(list(zip(x_test, y_test)), FLAGS.batch_size, 1)
			total_test_correct = 0
			for test_batch in test_batches:
				x_test_batch, y_test_batch = zip(*test_batch)
				num_test_correct = dev_step(x_test_batch, y_test_batch)
				total_test_correct += num_test_correct

def main(argv=None):
	train_cnn_multi()

if __name__ == '__main__':
    tf.app.run()