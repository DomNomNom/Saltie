import tensorflow as tf
import os



class NNAtba:

    num_hidden_1 = 500 # 1st layer num features
    num_hidden_2 = 1000 # 1st layer num features
    labels = None

    def create_weights(self):
        self.weights = {
            'h1': tf.Variable(tf.random_normal([self.state_dim, self.num_hidden_1])),
            'h2': tf.Variable(tf.random_normal([self.num_hidden_1, self.num_hidden_2])),
            'out': tf.Variable(tf.random_normal([self.num_hidden_2, self.num_actions])),
        }
        self.biases = {
            'b1': tf.Variable(tf.random_normal([self.num_hidden_1])),
            'b2': tf.Variable(tf.random_normal([self.num_hidden_2])),
            'out': tf.Variable(tf.random_normal([self.num_actions])),
        }

    def encoder(self, input):
        # Encoder Hidden layer with sigmoid activation #1
        layer_1 = tf.nn.sigmoid(tf.add(tf.matmul(input, self.weights['h1']), self.biases['b1']))

        layer_2 = tf.nn.sigmoid(tf.add(tf.matmul(layer_1, self.weights['h2']), self.biases['b2']))
        # Encoder Hidden layer with sigmoid activation #3
        layer_3 = tf.nn.sigmoid(tf.add(tf.matmul(layer_2, self.weights['out']), self.biases['out']))
        return layer_3

    """"
    This will be the example model framework with the needed functions but none of the code inside them
    You can copy this to implement your own model
    """
    def __init__(self, session,
                 state_dim,
                 num_actions,
                 summary_writer=None,
                 summary_every=100):


        self.sess = session
        self.num_actions = num_actions
        self.state_dim = state_dim
        self.input = tf.placeholder(tf.float32, shape=(None, self.state_dim))
        self.model = self.create_model(self.input)

        self.saver = tf.train.Saver()

        #file does not exist too lazy to add check

        model_file = self.get_model_path("trained_variables_drop.ckpt")
        print(model_file)
        if os.path.isfile(model_file + '.meta'):
            print('loading existing model')
            try:
                self.saver.restore(session, model_file)
            except:
                print('unable to load model')
        else:
            print('unable to load model')

        init = tf.global_variables_initializer()
        session.run(init)

    def create_training_model_copy(self, batch_size):
        self.labels = tf.placeholder(tf.int64, shape=(None, self.num_actions))

        cross_entropy = tf.nn.softmax_cross_entropy_with_logits(
            labels=self.labels, logits=self.logits, name='xentropy')
        loss = tf.reduce_mean(cross_entropy, name='xentropy_mean')

        return loss, self.input, self.labels


    def create_model(self, input):
        self.create_weights()
        self.logits = hidden_layers = self.encoder(input)
        result = tf.argmax(hidden_layers, 1)
        return result

    def store_rollout(self, state, last_action, reward):
        #I only care about the current state and action
        pass

    def sample_action(self, states):
        return self.sess.run(self.model, feed_dict={self.input: states})[0]

    def get_model_path(self, filename):
        # go up two levels
        dir_path = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        return dir_path + "\\training\\data\\nnatba\\" + filename

