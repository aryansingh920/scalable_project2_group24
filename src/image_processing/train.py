#!/usr/bin/env python3

import tensorflow.keras as keras  # type: ignore
import tensorflow as tf
import argparse
import random
import string
import numpy
import cv2
import os
import warnings

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)


# Build a Keras model given some parameters

def create_model(captcha_length, captcha_num_symbols, input_shape, model_depth=5, module_size=2):
    input_tensor = keras.Input(input_shape)
    x = input_tensor
    for i, module_length in enumerate([module_size] * model_depth):
        for j in range(module_length):
            x = keras.layers.Conv2D(
                32 * 2 ** min(i, 3), kernel_size=3, padding='same', kernel_initializer='he_uniform')(x)
            x = keras.layers.BatchNormalization()(x)
            x = keras.layers.Activation('relu')(x)
        x = keras.layers.MaxPooling2D(2)(x)

    x = keras.layers.Flatten()(x)
    x = [keras.layers.Dense(captcha_num_symbols, activation='softmax', name='char_%d' % (
            i + 1))(x) for i in range(captcha_length)]
    model = keras.Model(inputs=input_tensor, outputs=x)

    return model


# A Sequence represents a dataset for training in Keras


class ImageSequence(keras.utils.Sequence):
    def __init__(self, directory_name, batch_size, captcha_length, captcha_symbols, captcha_width, captcha_height):
        self.directory_name = directory_name
        self.batch_size = batch_size
        self.captcha_length = captcha_length
        self.captcha_symbols = captcha_symbols
        self.captcha_width = captcha_width
        self.captcha_height = captcha_height

        file_list = os.listdir(self.directory_name)
        self.files = dict(
            zip(map(lambda x: x.split('.')[0], file_list), file_list))
        self.used_files = []
        self.count = len(file_list)

    def __len__(self):
        return int(numpy.floor(self.count / self.batch_size))

    def __getitem__(self, idx):
        X = numpy.zeros((self.batch_size, self.captcha_height,
                         self.captcha_width, 3), dtype=numpy.float32)
        y = [numpy.zeros((self.batch_size, len(self.captcha_symbols)),
                         dtype=numpy.uint8) for _ in range(self.captcha_length)]

        for i in range(self.batch_size):
            if len(self.files) == 0:
                # Reset used files and refill the available files
                self.used_files.clear()
                file_list = os.listdir(self.directory_name)
                self.files = dict(
                    zip(map(lambda x: x.split('.')[0], file_list), file_list))

            random_image_label = random.choice(list(self.files.keys()))
            random_image_file = self.files[random_image_label]

            # We've used this image now, so we can't repeat it in this iteration
            self.used_files.append(self.files.pop(random_image_label))

            # Read and process the image
            raw_data = cv2.imread(os.path.join(
                self.directory_name, random_image_file))
            rgb_data = cv2.cvtColor(raw_data, cv2.COLOR_BGR2RGB)
            processed_data = numpy.array(rgb_data) / 255.0
            X[i] = processed_data

            # Handle filenames for labels
            random_image_label = random_image_label.split('_')[0]

            for j, ch in enumerate(random_image_label):
                y[j][i, :] = 0
                y[j][i, self.captcha_symbols.find(ch)] = 1

        return X, tuple(y)  # Ensure to return tuple for outputs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--width', help='Width of captcha image', type=int)
    parser.add_argument('--height', help='Height of captcha image', type=int)
    parser.add_argument(
        '--length', help='Length of captchas in characters', type=int)
    parser.add_argument(
        '--batch-size', help='How many images in training captcha batches', type=int)
    parser.add_argument(
        '--train-dataset', help='Where to look for the training image dataset', type=str)
    parser.add_argument(
        '--validate-dataset', help='Where to look for the validation image dataset', type=str)
    parser.add_argument('--output-model-name',
                        help='Where to save the trained model', type=str)
    parser.add_argument(
        '--input-model', help='Where to look for the input model to continue training', type=str)
    parser.add_argument(
        '--epochs', help='How many training epochs to run', type=int)
    parser.add_argument(
        '--symbols', help='File with the symbols to use in captchas', type=str)
    args = parser.parse_args()

    if args.width is None:
        print("Please specify the captcha image width")
        exit(1)

    if args.height is None:
        print("Please specify the captcha image height")
        exit(1)

    if args.length is None:
        print("Please specify the captcha length")
        exit(1)

    if args.batch_size is None:
        print("Please specify the training batch size")
        exit(1)

    if args.epochs is None:
        print("Please specify the number of training epochs to run")
        exit(1)

    if args.train_dataset is None:
        print("Please specify the path to the training data set")
        exit(1)

    if args.validate_dataset is None:
        print("Please specify the path to the validation data set")
        exit(1)

    if args.output_model_name is None:
        print("Please specify a name for the trained model")
        exit(1)

    if args.symbols is None:
        print("Please specify the captcha symbols file")
        exit(1)

    captcha_symbols = None
    with open(args.symbols) as symbols_file:
        # Read and strip any whitespace/newline
        captcha_symbols = symbols_file.readline().strip()

    with tf.device('/device:CPU:0'):
        model = create_model(args.length, len(
            captcha_symbols), (args.height, args.width, 3))

        if args.input_model is not None:
            model.load_weights(args.input_model)

        model.compile(loss='categorical_crossentropy',
                      optimizer=keras.optimizers.Adam(1e-3, amsgrad=True),
                      metrics=[keras.metrics.CategoricalAccuracy() for _ in range(args.length)])

        model.summary()

        training_data = ImageSequence(
            args.train_dataset, args.batch_size, args.length, captcha_symbols, args.width, args.height)
        validation_data = ImageSequence(
            args.validate_dataset, args.batch_size, args.length, captcha_symbols, args.width, args.height)

        callbacks = [
            keras.callbacks.EarlyStopping(patience=3),
            keras.callbacks.ModelCheckpoint(
                args.output_model_name + '.keras', save_best_only=False)
        ]

        # Save the model architecture to JSON
        with open(args.output_model_name + ".json", "w") as json_file:
            json_file.write(model.to_json())

        try:
            model.fit(
                x=training_data,
                validation_data=validation_data,
                epochs=args.epochs,
                callbacks=callbacks,
                # use_multiprocessing=True
            )

        except KeyboardInterrupt:
            print('KeyboardInterrupt caught, saving current weights as ' +
                  args.output_model_name + '_resume.h5')
            model.save_weights(args.output_model_name + '_resume.h5')


if __name__ == '__main__':
    main()