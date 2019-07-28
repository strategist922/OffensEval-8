import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.preprocessing import OneHotEncoder
from keras import optimizers
from keras import regularizers
from keras.preprocessing.sequence import pad_sequences
from keras.callbacks import ModelCheckpoint
from keras.layers import LSTM
from keras.layers import Dense
from keras.layers import TimeDistributed
from keras.layers import Bidirectional
from keras.layers import merge, Multiply
from keras.layers.core import *
from keras.layers.recurrent import LSTM
from keras.models import *
from keras.layers import concatenate
import time


def load_data():
    
    print("loading data")
    
    print('load embed')
    t = time.time()
    X_unpadded = np.load('../embeddings/Bert.npy')
    print(time.time() - t)
    
    data_training=pd.read_csv('../data-v1/offenseval-training-v1.tsv',delimiter='\t',encoding='utf-8')

    temp_a = {'OFF':1, 'NOT':0}
    temp_b = {'UNT':1, 'TIN':2}
    temp_c = {'IND':1, 'GRP':2, 'OTH':3}

    data_training['subtask_a'] = data_training['subtask_a'].map(temp_a)
    data_training['subtask_b'] = data_training['subtask_b'].map(temp_b)
    data_training['subtask_c'] = data_training['subtask_c'].map(temp_c)

    data_training = data_training.fillna(0)

    enc = OneHotEncoder(handle_unknown='ignore')
    enc.fit(np.array(data_training['subtask_a']).reshape(-1, 1))
    one_hot_subtask_a = enc.transform(np.array(data_training['subtask_a']).reshape(-1, 1)).toarray()
    
    print("data loaded")

    return X_unpadded[:120], one_hot_subtask_a[:120]


def padder(X_unpadded):
    
    print("start padding")
    t = time.time()
    max_sentence_len = 100
    X_word_embeddings_padded = []
    for i in range(0, 100, 50):
        print(i)
        padded = pad_sequences(X_unpadded[i:i+50], padding='pre', dtype='object', maxlen=max_sentence_len, truncating='post')
        X_word_embeddings_padded.append(padded)
    padded = pad_sequences(X_unpadded[i+50:], padding='pre', dtype='object', maxlen=max_sentence_len, truncating='post')
    X_word_embeddings_padded.append(padded)
    print(time.time() - t)
    print("padding done")
    
    return X_word_embeddings_padded


def attention_3d_block(inputs):
    # inputs.shape = (batch_size, time_steps, input_dim)
    input_dim = int(inputs.shape[2])
    a = Permute((2, 1))(inputs)
    a = Reshape((input_dim, TIME_STEPS))(a) # this line is not useful. It's just to know which dimension is what.
    a = Dense(TIME_STEPS, activation='softmax')(a)
    if SINGLE_ATTENTION_VECTOR:
        a = Lambda(lambda x: K.mean(x, axis=1), name='dim_reduction')(a)
        a = RepeatVector(input_dim)(a)
    a_probs = Permute((2, 1), name='attention_vec')(a)
    #output_attention_mul = merge([inputs, a_probs], name='attention_mul', mode='mul')
    #output_attention_mul = concatenate([inputs, a_probs], mode='mul', name='attention_mul')
    output_attention_mul = Multiply()([inputs, a_probs])

    return output_attention_mul


def make_model(X, Y):
    
    inputs_layer = Input(shape=(TIME_STEPS, INPUT_DIM, ))
    lstm_out = Bidirectional(LSTM(lstm_units, dropout=0.5, recurrent_dropout=0.5, return_sequences=True), merge_mode='concat')(inputs_layer)
    attention_mul = attention_3d_block(lstm_out)
    attention_mul = Flatten()(attention_mul)
    output = Dense(2, activation="sigmoid")(attention_mul)
    model = Model(inputs=[inputs_layer], outputs=output)

    #complie model
    adam = optimizers.Adam(lr=0.001)
    model.compile(optimizer=adam, loss='categorical_crossentropy', metrics=['accuracy'])

    #checkpoint
    filepath="weights-improvement-BERT-a-{epoch:02d}-{val_acc:.2f}.hdf5"
    checkpoint = ModelCheckpoint(filepath, monitor='val_acc', verbose=1, save_best_only=True, mode='max')
    callbacks_list = [checkpoint]
    
    #print(model.summary())
    
    #fit the model
    model.fit(x=X, y=Y, validation_split=0.33,	batch_size=16, epochs=20, callbacks=callbacks_list, verbose=0)
    
    #plot
    plt.subplot(1, 2, 1)
    plt.plot(model.history.history['val_loss'], label = 'val_loss')
    plt.plot(model.history.history['loss'], label = 'loss')
    plt.title("BiLSTM - Attention (subtask_a) model (loss='categorical_crossentropy', optimizer='Adam', metrics=['accuracy']) \n elmo pre-trained-vectors")
    plt.xlabel("epoch")
    plt.ylabel("loss")
    plt.legend()
    plt.subplot(1, 2, 2)
    plt.plot(model.history.history['acc'], label = 'acc')
    plt.plot(model.history.history['val_acc'], label = 'val_acc')
    plt.xlabel("epoch")
    plt.ylabel("acc")
    plt.legend()
    #plt.show()
    plt.savefig('Bi_LSTM attention | BERT')


X_unpadded, Y = load_data()
X = padder(X_unpadded)
max_sentence_len = 100
TIME_STEPS, INPUT_DIM, lstm_units, SINGLE_ATTENTION_VECTOR = max_sentence_len, len(X[0][0]), 10, False
make_model(X, Y)
    
