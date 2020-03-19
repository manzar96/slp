import random
import torch
import torch.nn as nn
import torch.nn.functional as F

from slp.modules.rnn import WordRNN2
from slp.modules.embed import Embed
from slp.modules.pooling import L2PoolingLayer, Maxout2

class Encoder(nn.Module):
    def __init__(self, input_size, vocab_size, hidden_size, embedding=None,
                 embeddings_dropout=.1,
                 finetune_embeddings=False, num_layers=1, batch_first=True,
                 bidirectional=False, dropout=0, attention=None, device='cpu'):
        super(Encoder, self).__init__()
        self.hidden_size = hidden_size
        self.bidirectional = bidirectional
        self.device = device
        self.word_rnn = WordRNN2(embedding_dim=input_size,
                                 vocab_size=vocab_size,
                                 hidden_size=hidden_size,
                                 embeddings=embedding,
                                 embeddings_dropout=embeddings_dropout,
                                 finetune_embeddings=finetune_embeddings,
                                 batch_first=batch_first,
                                 layers=num_layers,
                                 bidirectional=bidirectional,
                                 rnn_type='gru',
                                 merge_bi='cat', dropout=dropout,
                                 attention=attention,
                                 device=self.device)

    def forward(self, inputs, lengths):
        last_out, hidden = self.word_rnn(inputs, lengths)
        #3.  Episis na tsekarw an kanthe fora to hidden einai 0 !!!

        return last_out, hidden


class ContextEncoder(nn.Module):
    def __init__(self, input_size, hidden_size, num_layers=1, batch_first=True,
                 bidirectional=False, dropout=0, attention=None,
                 rnn_type='gru', device='cpu'):
        super(ContextEncoder, self).__init__()
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.batch_first = batch_first
        self.bidirectional = bidirectional
        self.dropout = dropout
        self.attention = attention
        self.rnn_type = rnn_type
        self.device = device

        # if attention needed then use this!!!
        """
        self.rnn = RNN(emb_size, hidden_size, batch_first, num_layers,
               bidirectional, merge_bi='cat', dropout=dropout,
               rnn_type=rnn_type, device=device)
        """
        if self.rnn_type == 'lstm':
            self.rnn = nn.LSTM(input_size=self.input_size,
                               hidden_size=self.hidden_size,
                               num_layers=self.num_layers,
                               bidirectional=self.bidirectional,
                               dropout=self.dropout,
                               batch_first=self.batch_first)
        elif self.rnn_type == 'rnn':
            self.rnn = nn.RNN(input_size=self.input_size,
                              hidden_size=self.hidden_size,
                              num_layers=self.num_layers,
                              bidirectional=self.bidirectional,
                              dropout=self.dropout,
                              batch_first=self.batch_first)
        elif self.rnn_type == 'gru':
            self.rnn = nn.GRU(input_size=self.input_size,
                              hidden_size=self.hidden_size,
                              num_layers=self.num_layers,
                              bidirectional=self.bidirectional,
                              dropout=self.dropout,
                              batch_first=self.batch_first)


    def forward(self, encoded_context):
        # to encoded_context einai ena sequence apo representations twn query.
        # se auth thn periptwsi to seq len einai 2 afou exw 2 queries!!
        #encoded_context shape: [bactchsize,seqlen,hiddensize of encoder]
        # Se auth thn periptwsi den xreiazetai pack padded seq!!!!
        out, hidden = self.rnn(encoded_context)
        return out, hidden


class Decoder(nn.Module):
    """
    This implementation of the decoder is only used for the referenced paper in
    HRED class. That's because of the used of some linear layers, max-out
    methods! The decoder also does not uses WordRnn class as it should
    because we wanted the embedding layer to be used on the decoder class.

    """
    def __init__(self, vocab_size, emb_size, hidden_size, embeddings=None,
                 embeddings_dropout=.1, finetune_embeddings=False,
                 num_layers=1, tc_ratio=1., batch_first=True,
                 bidirectional=False, dropout=0, attention=None,
                 merge_bi='cat', device='cpu'):
        super(Decoder, self).__init__()
        self.hidden_size = hidden_size
        self.bidirectional = bidirectional
        self.teacher_forcing_ratio = tc_ratio
        self.batch_first = batch_first
        self.device = device
        self.word_rnn = WordRNN2(emb_size,vocab_size,hidden_size,
                                 embeddings,
                                 embeddings_dropout,
                                finetune_embeddings, batch_first,
                                num_layers, bidirectional, merge_bi=merge_bi,
                                dropout=dropout, attention=attention,
                                device=device)


    def forward_step(self, dec_input, dec_lengths, dec_hidden, enc_output):

        # we hav eto change the word_rnn not to receive lengths argument if
        # its not needed!!!!
        dec_out, hidden = self.word_rnn(dec_input, dec_lengths, dec_hidden,
                                        enc_output)
        return dec_out, hidden

    def forward(self, dec_input, dec_lengths, targets, target_lens,
                dec_hidden=None, enc_output=None):
        """
        dec_hidden is used for decoder's hidden state initialization!
        Usually the encoder's last (from the last timestep) hidden state is
        passed to decoder's hidden state.
        enc_output: argument is passed if we want to have attention (it is
        used only for attention, if you don't want to have attention on your
        model leave it as is!)
        dec_lengths: during decoding lengths is not mandatory. however we
        pass this argument because word rnn receives as input the lengths of
        input too. (We cannot skip giving lengths because in another
        situations where samples are padded we want to receive the last
        unpadded element for every sample in the batch and not the one for
        t=seq_len)
        """
        max_seq_len = targets.shape[1]
        decoder_outputs = []

        for i in range(0, max_seq_len):
            use_teacher_forcing = True if (
                    random.random() < self.teacher_forcing_ratio) else False

            if use_teacher_forcing:
                dec_out, dec_hidden = self.forward_step(dec_input, dec_lengths,
                                                        dec_hidden, enc_output)

                dec_input = targets[:, i]
                dec_lengths = torch.ones(targets.shape[0], 1)

                # use decoder output

            else:
                pass


        #return decoder_outputs,decoder_hidden


class HREDDecoder(nn.Module):
    """
    This implementation of the decoder is only used for the referenced paper in
    HRED class. That's because of the used of some linear layers, max-out
    methods! The decoder also does not uses WordRnn class as it should
    because we wanted the embedding layer to be used on the decoder class.

    """

    def __init__(self, options, vocab_size, emb_size, hidden_size,
                 embeddings=None,
                 embeddings_dropout=.1, finetune_embeddings=False,
                 num_layers=1, tc_ratio=1., batch_first=True,
                 bidirectional=False, dropout=0, attention=None,
                 merge_bi='cat', rnn_type="gru", device='cpu',encoder=None):
        super(HREDDecoder, self).__init__()

        self.vocab_size = vocab_size
        self.emb_size = emb_size
        self.hidden_size = hidden_size
        self.embeddings = embeddings
        self.embeddings_dropout = embeddings_dropout
        self.finetune_embeddings = finetune_embeddings
        self.num_layers = num_layers
        self.teacher_forcing_ratio = tc_ratio
        self.batch_first = batch_first
        self.bidirectional = bidirectional
        self.dropout = dropout
        self.attention = attention
        self.merge_bi = merge_bi
        self.rnn_type = rnn_type
        self.device = device
        self.pretraining = options.pretraining
        if self.rnn_type == 'lstm':
            self.rnn = nn.LSTM(input_size=self.emb_size,
                               hidden_size=self.hidden_size,
                               num_layers=self.num_layers,
                               bidirectional=self.bidirectional,
                               dropout=self.dropout,
                               batch_first=self.batch_first)
        elif self.rnn_type == 'rnn':
            self.rnn = nn.RNN(input_size=self.emb_size,
                              hidden_size=self.hidden_size,
                              num_layers=self.num_layers,
                              bidirectional=self.bidirectional,
                              dropout=self.dropout,
                              batch_first=self.batch_first)
        elif self.rnn_type == 'gru':
            self.rnn = nn.GRU(input_size=self.emb_size,
                              hidden_size=self.hidden_size,
                              num_layers=self.num_layers,
                              bidirectional=self.bidirectional,
                              dropout=self.dropout,
                              batch_first=self.batch_first)

        self.embed_in = Embed(num_embeddings=self.vocab_size,
                              embedding_dim=self.emb_size,
                              embeddings=self.embeddings,
                              dropout=self.embeddings_dropout,
                              trainable=self.finetune_embeddings)


        #self.dec_to_emb2 = nn.Linear(self.hidden_size, self.emb_size*2, False)
        #self.cont_to_emb2 = nn.Linear(options.contenc_hidden_size,
        #                              self.emb_size*2, False)
        #self.emb_to_emb2 = nn.Linear(self.emb_size, self.emb_size*2, True)

        #self.embed_out = nn.Linear(self.emb_size, self.vocab_size, False)
        #self.max_out = Maxout2(self.emb_size*2, self.emb_size, 2)
        self.output_layer = nn.Linear(self.hidden_size, self.vocab_size)


    def forward(self, dec_input, targets, target_lens, dec_hidden=None,
                enc_output=None):
        """
        dec_hidden is used for decoder's hidden state initialization!
        Usually the encoder's last (from the last timestep) hidden state is
        passed to decoder's hidden state.
        enc_output: argument is passed if we want to have attention (it is
        used only for attention, if you don't want to have attention on your
        model leave it as is!)
        dec_lengths: during decoding lengths is not mandatory. however we
        pass this argument because word rnn receives as input the lengths of
        input too. (We cannot skip giving lengths because in another
        situations where samples are padded we want to receive the last
        unpadded element for every sample in the batch and not the one for
        t=seq_len)
        """

        context_encoded = dec_hidden
        max_seq_len = targets.shape[1]
        decoder_outputs = []
        for i in range(0, max_seq_len):
            use_teacher_forcing = True if (
                    random.random() < self.teacher_forcing_ratio) else False

            if use_teacher_forcing:
                input_embed = self.embed_in(dec_input)
                if enc_output is None:
                    dec_out, dec_hidden = self.rnn(input_embed, hx=dec_hidden)
                else:
                    assert False, "Attention is not implemented"

                # if not self.pretraining:
                #     # ω(dm,n−1, wm,n−1) = Ho dm,n−1 + Eo wm,n−1 + bo   (olo auto se
                #     # diastasi emb_size*2
                #     emb_inf_vec = self.emb_to_emb2(input_embed).squeeze(dim=1)
                #     dec_inf_vec = self.dec_to_emb2(dec_out).squeeze(dim=1)
                #     cont_inf_vec = self.cont_to_emb2(context_encoded).squeeze(
                #         dim=0)
                #
                #     total_out = dec_inf_vec + cont_inf_vec + emb_inf_vec
                #
                #     #after max_out total_out dims:  emb_size
                #     total_out = self.max_out(total_out)
                # else:
                #
                #     total_out = self.dec_to_emb2(dec_out).squeeze(dim=1)
                #     total_out = self.max_out(total_out)

                # out = self.embed_out(total_out)

                out = self.output_layer(dec_out.squeeze(dim=1))
                decoder_outputs.append(out)

                dec_input = targets[:, i].unsqueeze(dim=1)

            else:
                assert False, "not implemented yet!!"
                # TODO: no teacher forcing case!!!

        dec_output = torch.stack(decoder_outputs).transpose(0,1)
        del decoder_outputs
        return dec_output


class HREDSeq2Seq(nn.Module):
    def __init__(self, options, emb_size, vocab_size, enc_embeddings,
                 dec_embeddings, sos_index, device):
        super(HREDSeq2Seq, self).__init__()
        self.enc = Encoder(input_size=emb_size,
                           vocab_size=vocab_size,
                           embedding=enc_embeddings,
                           hidden_size=options.enc_hidden_size,
                           embeddings_dropout=options.embeddings_dropout,
                           finetune_embeddings=options.enc_finetune_embeddings,
                           num_layers=options.enc_num_layers,
                           batch_first=options.batch_first,
                           bidirectional=options.enc_bidirectional,
                           dropout=options.enc_dropout,
                           device=device)

        self.cont_enc = ContextEncoder(input_size=options.contenc_input_size,
                                       hidden_size=options.contenc_hidden_size,
                                       num_layers=options.contenc_num_layers,
                                       batch_first=options.batch_first,
                                       bidirectional=
                                       options.contenc_bidirectional,
                                       dropout=options.contenc_dropout,
                                       rnn_type=options.contenc_rnn_type,
                                       device=device)

        self.dec = HREDDecoder(options, vocab_size=vocab_size,
                           emb_size=emb_size,
                           hidden_size=options.dec_hidden_size,
                           embeddings=dec_embeddings,
                           embeddings_dropout=options.embeddings_dropout,
                           finetune_embeddings=options.dec_finetune_embeddings,
                           num_layers=options.dec_num_layers,
                           tc_ratio=options.teacherforcing_ratio,
                           batch_first=options.batch_first,
                           bidirectional=options.dec_bidirectional,
                           dropout=options.dec_dropout,
                           merge_bi=options.dec_merge_bi,
                           rnn_type=options.dec_rnn_type,
                           device=device)

        if options.shared_emb:
            self.dec.embed_in = self.enc.word_rnn.embed

        if options.shared:
            self.dec.embed_in = self.enc.word_rnn.embed
            self.dec.rnn = self.enc.word_rnn.rnn.rnn

        self.batch_first = options.batch_first
        self.options = options
        self.sos_index = sos_index
        self.device = device

        # we use a linear layer and tanh act function to initialize the
        # hidden of the decoder.
        # paper reference: A Hierarchical Recurrent Encoder-Decoder
        # for Generative Context-Aware Query Suggestion, 2015
        # dm,0 = tanh(D0sm−1 + b0)  (equation 7)

        self.enc_to_dec = nn.Linear(self.enc.hidden_size,
                                    self.dec.hidden_size)
        self.cont_enc_to_dec = nn.Linear(self.cont_enc.hidden_size,
                                         self.dec.hidden_size, bias=True)
        self.tanh = nn.Tanh()

        if self.options.pretraining:
            for param in self.cont_enc.rnn.parameters():
                if param.requires_grad:
                    param.requires_grad = False
            for param in self.cont_enc_to_dec.parameters():
                if param.requires_grad:
                    param.requires_grad = False
        else:
            for param in self.cont_enc.rnn.parameters():
                param.requires_grad = True
            for param in self.cont_enc_to_dec.parameters():
                param.requires_grad = True

    def forward(self, u1, l1, u2, l2, u3, l3):
        if self.options.pretraining:
            _, hidden = self.enc(u2, l2)

            """
            we take the last layer of the hidden state!
            (Supposing it is a gru)
            """
            if self.options.enc_bidirectional:
                hidden = hidden[-2:]
            else:
                hidden = hidden[-1]

            dec_init_hidden = hidden.view(self.options.dec_num_layers,
                                          u3.shape[0],
                                          self.options.dec_hidden_size)
            # dec_init_hidden = self.tanh(self.enc_to_dec(hidden))
            # dec_init_hidden = hidden[:self.dec.num_layers]

            #decoder_input = torch.zeros(u3.shape[0], 1).long()
            decoder_input = torch.tensor([self.sos_index for _ in range(
                u3.shape[0])]).long().unsqueeze(dim=1)
            decoder_input = decoder_input.to(self.device)

            dec_out = self.dec(decoder_input, u3, l3, dec_init_hidden)

        else:
            _, hidden1 = self.enc(u1, l1)
            _, hidden2 = self.enc(u2, l2)

            """
            we take the last layer of the hidden state!
            (Supposing it is a gru)
            """
            if self.options.enc_bidirectional:
                hidden1 = hidden1[-2:]
                hidden2 = hidden2[-2:]
            else:
                hidden1 = hidden1[-1]
                hidden2 = hidden2[-1]

            hidden1 = hidden1.unsqueeze(dim=1)
            hidden2 = hidden2.unsqueeze(dim=1)
            context_input = torch.cat((hidden1, hidden2), dim=1)

            _, contenc_hidden = self.cont_enc(context_input)

            """
            we take the last layer of the hidden state!
            (Supposing it is a gru)
            """
            if self.options.contenc_bidirectional:
                contenc_hidden = contenc_hidden[-2:]
            else:
                contenc_hidden = contenc_hidden[-1]

            dec_init_hidden = self.tanh(self.cont_enc_to_dec(contenc_hidden))
            # edw mia view to dec_init_hidden
            dec_init_hidden = dec_init_hidden.view(self.options.dec_num_layers,
                                                   u3.shape[0],
                                                   self.options.dec_hidden_size)
            # edw isws thelei contiguous!!!

            # edw ftiaxnw to input (nomizw einai midenika alla sto paper vazei 1)
            # decoder_input = [self.sos_index for _ in range(u3.shape[0])]
            # decoder_input = torch.tensor(decoder_input).long()
            # decoder_input = decoder_input.unsqueeze(dim=1)
            # decoder_input = decoder_input.to(self.device)

            #decoder_input = torch.zeros(u3.shape[0], 1).long()
            decoder_input = torch.tensor([self.sos_index for _ in range(
                u3.shape[0])]).long().unsqueeze(dim=1)
            decoder_input = decoder_input.to(self.device)

            dec_out = self.dec(decoder_input, u3, l3, dec_init_hidden)

        return dec_out

"""
This one passes question from the context encoder! not so good, because it 
has no logic.
"""
class HREDSeq2Seq_Context(nn.Module):
    def __init__(self, options, emb_size, vocab_size, enc_embeddings,
                 dec_embeddings, sos_index, device):
        super(HREDSeq2Seq_Context, self).__init__()
        self.enc = Encoder(input_size=emb_size,
                           vocab_size=vocab_size,
                           embedding=enc_embeddings,
                           hidden_size=options.enc_hidden_size,
                           embeddings_dropout=options.embeddings_dropout,
                           finetune_embeddings=options.enc_finetune_embeddings,
                           num_layers=options.enc_num_layers,
                           batch_first=options.batch_first,
                           bidirectional=options.enc_bidirectional,
                           dropout=options.enc_dropout,
                           device=device)

        self.cont_enc = ContextEncoder(input_size=options.contenc_input_size,
                                       hidden_size=options.contenc_hidden_size,
                                       num_layers=options.contenc_num_layers,
                                       batch_first=options.batch_first,
                                       bidirectional=
                                       options.contenc_bidirectional,
                                       dropout=options.contenc_dropout,
                                       rnn_type=options.contenc_rnn_type,
                                       device=device)

        self.dec = HREDDecoder(options, vocab_size=vocab_size,
                               emb_size=emb_size,
                               hidden_size=options.dec_hidden_size,
                               embeddings=dec_embeddings,
                               embeddings_dropout=options.embeddings_dropout,
                               finetune_embeddings=options.dec_finetune_embeddings,
                               num_layers=options.dec_num_layers,
                               tc_ratio=options.teacherforcing_ratio,
                               batch_first=options.batch_first,
                               bidirectional=options.dec_bidirectional,
                               dropout=options.dec_dropout,
                               merge_bi=options.dec_merge_bi,
                               rnn_type=options.dec_rnn_type,
                               device=device)

        self.batch_first = options.batch_first
        self.options = options
        self.sos_index = sos_index
        self.device = device
        # we use a linear layer and tanh act function to initialize the
        # hidden of the decoder.
        # paper reference: A Hierarchical Recurrent Encoder-Decoder
        # for Generative Context-Aware Query Suggestion, 2015
        # dm,0 = tanh(D0sm−1 + b0)  (equation 7)
        self.cont_enc_to_dec = nn.Linear(self.cont_enc.hidden_size,
                                         self.dec.hidden_size, bias=True)
        self.tanh = nn.Tanh()

        # if self.options.pretraining:
        #     for param in self.cont_enc.rnn.parameters():
        #         if param.requires_grad:
        #             param.requires_grad = False

    def forward(self, u1, l1, u2, l2, u3, l3):
        if self.options.pretraining:
            _, hidden = self.enc(u2, l2)

            """
            we take the last layer of the hidden state!
            (Supposing it is a gru)
            """
            if self.options.enc_bidirectional:
                hidden = hidden[-2:]
            else:
                hidden = hidden[-1]

            
            _, contenc_hidden = self.cont_enc(hidden)

            if self.options.contenc_bidirectional:
                contenc_hidden = contenc_hidden[-2:]
            else:
                contenc_hidden = contenc_hidden[-1]

            dec_init_hidden = self.tanh(self.cont_enc_to_dec(contenc_hidden))
            dec_init_hidden = dec_init_hidden.view(self.options.dec_num_layers,
                                                   u3.shape[0],
                                                   self.options.dec_hidden_size)

            # dec_init_hidden = hidden.view(self.options.dec_num_layers,
            #                               u3.shape[0],
            #                               self.options.dec_hidden_size)

            # decoder_input = torch.zeros(u3.shape[0], 1).long()
            decoder_input = torch.tensor([self.sos_index for _ in range(
                u3.shape[0])]).long().unsqueeze(dim=1)
            decoder_input = decoder_input.to(self.device)

            dec_out = self.dec(decoder_input, u3, l3, dec_init_hidden)

        else:
            _, hidden1 = self.enc(u1, l1)
            _, hidden2 = self.enc(u2, l2)

            """
            we take the last layer of the hidden state!
            (Supposing it is a gru)
            """
            if self.options.enc_bidirectional:
                hidden1 = hidden1[-2:]
                hidden2 = hidden2[-2:]
            else:
                hidden1 = hidden1[-1]
                hidden2 = hidden2[-1]

            hidden1 = hidden1.unsqueeze(dim=1)
            hidden2 = hidden2.unsqueeze(dim=1)
            context_input = torch.cat((hidden1, hidden2), dim=1)

            _, contenc_hidden = self.cont_enc(context_input)

            """
            we take the last layer of the hidden state!
            (Supposing it is a gru)
            """
            if self.options.contenc_bidirectional:
                contenc_hidden = contenc_hidden[-2:]
            else:
                contenc_hidden = contenc_hidden[-1]

            dec_init_hidden = self.tanh(self.cont_enc_to_dec(contenc_hidden))
            # edw mia view to dec_init_hidden
            dec_init_hidden = dec_init_hidden.view(self.options.dec_num_layers,
                                                   u3.shape[0],
                                                   self.options.dec_hidden_size)
            # edw isws thelei contiguous!!!

            # edw ftiaxnw to input (nomizw einai midenika alla sto paper vazei 1)
            # decoder_input = [self.sos_index for _ in range(u3.shape[0])]
            # decoder_input = torch.tensor(decoder_input).long()
            # decoder_input = decoder_input.unsqueeze(dim=1)
            # decoder_input = decoder_input.to(self.device)

            # decoder_input = torch.zeros(u3.shape[0], 1).long()
            decoder_input = torch.tensor([self.sos_index for _ in range(
                u3.shape[0])]).long().unsqueeze(dim=1)
            decoder_input = decoder_input.to(self.device)

            dec_out = self.dec(decoder_input, u3, l3, dec_init_hidden)

        return dec_out

class GreedySearchHREDSeq2Seq(nn.Module):
    def __init__(self, hred, device):
        super(GreedySearchHREDSeq2Seq, self).__init__()

        self.enc = hred.enc
        self.cont_enc = hred.cont_enc
        self.dec = GreedySearchHREDDecoder(hred.dec, device)
        self.batch_first = hred.batch_first
        self.options = hred.options
        self.sos_index = hred.sos_index
        self.first_time = True
        # we use a linear layer and tanh act function to initialize the
        # hidden of the decoder.
        # paper reference: A Hierarchical Recurrent Encoder-Decoder
        # for Generative Context-Aware Query Suggestion, 2015
        # dm,0 = tanh(D0sm−1 + b0)  (equation 7)
        self.cont_enc_to_dec = hred.cont_enc_to_dec
        self.tanh = hred.tanh

        self.device = device

    def forward(self, input_seq1, input_length1, input_seq2, input_length2):
        if self.first_time:
            _, hidden = self.enc(input_seq2, input_length2)

            """
            we take the last layer of the hidden state!
            (Supposing it is a gru)
            """
            if self.options.enc_bidirectional:
                hidden = hidden[-2:]
            else:
                hidden = hidden[-1]

            dec_init_hidden = hidden.view(self.options.dec_num_layers,
                                          1,
                                          self.options.dec_hidden_size)

            decoder_input = torch.zeros(1, 1).long()
            decoder_input = decoder_input.to(self.device)
            dec_tokens, dec_scores = self.dec(decoder_input, dec_init_hidden)
            self.first_time = False
        else:
            _, hidden1 = self.enc(input_seq1, input_length1)
            _, hidden2 = self.enc(input_seq2, input_length2)

            """
                   we take the last layer of the hidden state!
                   (Supposing it is a gru)
            """
            if self.options.enc_bidirectional:
                hidden1 = hidden1[-2:]
                hidden2 = hidden2[-2:]
            else:
                hidden1 = hidden1[-1]
                hidden2 = hidden2[-1]

            hidden1 = hidden1.unsqueeze(dim=1)
            hidden2 = hidden2.unsqueeze(dim=1)
            context_input = torch.cat((hidden1, hidden2), dim=1)

            _, contenc_hidden = self.cont_enc(context_input)

            """
            we take the last layer of the hidden state!
            (Supposing it is a gru)
            """
            if self.options.contenc_bidirectional:
                contenc_hidden = contenc_hidden[-2:]
            else:
                contenc_hidden = contenc_hidden[-1]

            dec_init_hidden = self.tanh(self.cont_enc_to_dec(contenc_hidden))

            dec_init_hidden = dec_init_hidden.view(self.options.dec_num_layers,
                                                   1,
                                                   self.options.dec_hidden_size)
            # edw isws thelei contiguous!!!

            # decoder_input = torch.zeros(1, 1).long()
            # decoder_input = decoder_input.to(self.device)

            decoder_input = torch.tensor([self.sos_index]).long().unsqueeze(dim=1)
            decoder_input = decoder_input.to(self.device)

            dec_tokens, dec_scores = self.dec(decoder_input, dec_init_hidden)
        return dec_tokens, dec_scores


class GreedySearchHREDDecoder(nn.Module):
    def __init__(self, decoder, device):
        super(GreedySearchHREDDecoder, self).__init__()

        self.dec = decoder
        self.max_length = 11
        self.device = device

    def forward(self, dec_input, dec_hidden=None, enc_output=None):
        """
        dec_hidden is used for decoder's hidden state initialization!
        Usually the encoder's last (from the last timestep) hidden state is
        passed to decoder's hidden state.
        enc_output: argument is passed if we want to have attention (it is
        used only for attention, if you don't want to have attention on your
        model leave it as is!)
        dec_lengths: during decoding lengths is not mandatory. however we
        pass this argument because word rnn receives as input the lengths of
        input too. (We cannot skip giving lengths because in another
        situations where samples are padded we want to receive the last
        unpadded element for every sample in the batch and not the one for
        t=seq_len)
        """
        context_encoded = dec_hidden
        decoder_outputs = []

        all_tokens = torch.zeros([0], device=self.device, dtype=torch.long)
        all_scores = torch.zeros([0], device=self.device)

        for i in range(0, self.max_length):

            input_embed = self.dec.embed_in(dec_input)
            if enc_output is None:
                dec_out, dec_hidden = self.dec.rnn(input_embed,
                                                   hx=dec_hidden)
            else:
                assert False, "Attention is not implemented"

            # ω(dm,n−1, wm,n−1) = Ho dm,n−1 + Eo wm,n−1 + bo   (olo auto se
            # diastasi emb_size*2
            # emb_inf_vec = self.dec.emb_to_emb2(input_embed).squeeze(dim=1)
            # dec_inf_vec = self.dec.dec_to_emb2(dec_out).squeeze(dim=1)
            # cont_inf_vec = self.dec.cont_to_emb2(context_encoded).squeeze(
            #     dim=0)
            #
            # total_out = dec_inf_vec + cont_inf_vec + emb_inf_vec

            #after max_out total_out dims:  emb_size
            # total_out = self.dec.max_out(total_out)
            # out = self.dec.embed_out(total_out)

            out = self.dec.output_layer(dec_out.squeeze(dim=1))
            out = F.softmax(out, dim=1)

            decoder_scores, dec_input = torch.max(out, dim=1)
            all_tokens = torch.cat((all_tokens, dec_input), dim=0)
            all_scores = torch.cat((all_scores, decoder_scores), dim=0)
            dec_input = torch.unsqueeze(dec_input, 0)

        return all_tokens, all_scores
