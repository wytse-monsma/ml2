import tensorflow as tf
import os

# TO DO:
# Add value function estimation head of neural network, as used by the PPO algorithm

def create_cnn(input_shape, num_channels, num_actions, hidden_units):
    # Define input layer for spatial data
    spatial_input = tf.keras.layers.Input(shape=input_shape, name='spatial_input')

    # Build convolutional layers for feature extraction from spatial data
    x = spatial_input
    x = tf.keras.layers.Conv2D(filters=32, kernel_size=3, activation='relu', padding='same', kernel_initializer='he_normal')(x)
    x = tf.keras.layers.MaxPooling2D(pool_size=2)(x)
    x = tf.keras.layers.Conv2D(filters=64, kernel_size=3, activation='relu', padding='same', kernel_initializer='he_normal')(x)
    x = tf.keras.layers.MaxPooling2D(pool_size=2)(x)

    # Flatten before fully connected layers
    x = tf.keras.layers.Flatten()(x)

    # Define input layer for non-spatial data
    non_spatial_input = tf.keras.layers.Input(shape=(num_channels,), name='non_spatial_input')

    # Concatenate output from convolutional layers with non-spatial data
    merged_input = tf.keras.layers.concatenate([x, non_spatial_input], axis=-1)

    # Add fully connected layers for further processing
    x = tf.keras.layers.Dense(hidden_units, activation='relu', kernel_initializer='he_normal')(merged_input)
    x = tf.keras.layers.Dropout(0.5)(x)
    x = tf.keras.layers.Dense(hidden_units, activation='relu', kernel_initializer='he_normal')(x)

    # Output layer for action probabilities
    output_layer = tf.keras.layers.Dense(num_actions, activation='softmax', name='output_layer')(x)

    # Create and compile the model
    model = tf.keras.Model(inputs=[spatial_input, non_spatial_input], outputs=output_layer)
    model.compile(optimizer='adam', loss='categorical_crossentropy', metrics=['accuracy'])

    return model


# # Example usage:
# # Specify the input shape, number of channels, and other parameters
# input_shape = (15, 15, 1)
# num_channels = 3  # Assuming 3 channels for spatial data
# num_actions = 6  # Assuming 6 possible actions (adjust as needed)

# # Create the model
# model = create_cnn(input_shape=input_shape, num_channels=num_channels, num_actions=num_actions)

# # Display the model summary
# model.summary()

# # Save the model architecture as an image file
# plot_model(model, to_file='model_architecture.png', show_shapes=True, show_layer_names=True)


# # TEST

# import numpy as np
# import time

# # Initialize the model with random weights
# model.build(input_shape=[(None,) + input_shape, (None, num_channels)])
# model.summary()

# # # Generate a random test sample
# # spatial_data = np.random.rand(1, *input_shape)
# # non_spatial_data = np.random.rand(1, num_channels)

# # # Measure the time it takes to get the output for a single test sample
# # start_time = time.time()
# # #output_probabilities = model.predict([spatial_data, non_spatial_data])

# # output_probabilities = model([spatial_data, non_spatial_data], training=False)

# # end_time = time.time()

# # Generate a random test sample
# spatial_data = np.random.rand(1, *input_shape)
# non_spatial_data = np.random.rand(1, num_channels)

# # Convert NumPy arrays to TensorFlow tensors
# spatial_data_tensor = tf.constant(spatial_data, dtype=tf.float32)
# non_spatial_data_tensor = tf.constant(non_spatial_data, dtype=tf.float32)

# # Measure the time it takes to get the output for a single test sample
# start_time = time.time()

# # Perform inference using tensors as input
# output_probabilities = model([spatial_data_tensor, non_spatial_data_tensor], training=False)

# end_time = time.time()

# # Convert the output to a NumPy array
# output_probabilities_np = output_probabilities.numpy()

# # Display the output probabilities
# print("Output Probabilities:", output_probabilities)

# # Display the time taken for prediction
# print("Time taken for prediction:", end_time - start_time, "seconds")