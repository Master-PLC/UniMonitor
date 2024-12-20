import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.nn.utils import weight_norm

from layers.Decoders import OutputBlock


class Chomp1d(nn.Module):
    def __init__(self, chomp_size):
        super(Chomp1d, self).__init__()
        self.chomp_size = chomp_size

    def forward(self, x):
        return x[:, :, :-self.chomp_size].contiguous()


class TemporalBlock(nn.Module):
    def __init__(self, n_inputs, n_outputs, kernel_size, stride, dilation, padding, dropout=0.2):
        super(TemporalBlock, self).__init__()
        self.conv1 = weight_norm(
            nn.Conv1d(n_inputs, n_outputs, kernel_size, stride=stride, padding=padding, dilation=dilation)
        )
        self.chomp1 = Chomp1d(padding)
        self.relu1 = nn.ReLU()
        self.dropout1 = nn.Dropout(dropout)

        self.conv2 = weight_norm(
            nn.Conv1d(n_outputs, n_outputs, kernel_size, stride=stride, padding=padding, dilation=dilation)
        )
        self.chomp2 = Chomp1d(padding)
        self.relu2 = nn.ReLU()
        self.dropout2 = nn.Dropout(dropout)

        self.net = nn.Sequential(
            self.conv1, self.chomp1, self.relu1, self.dropout1,
            self.conv2, self.chomp2, self.relu2, self.dropout2
        )
        self.downsample = nn.Conv1d(n_inputs, n_outputs, 1) \
            if n_inputs != n_outputs else None
        self.relu = nn.ReLU()
        self.init_weights()

    def init_weights(self):
        self.conv1.weight.data.normal_(0, 0.01)
        self.conv2.weight.data.normal_(0, 0.01)
        if self.downsample is not None:
            self.downsample.weight.data.normal_(0, 0.01)

    def forward(self, x):
        out = self.net(x)
        res = x if self.downsample is None else self.downsample(x)
        return self.relu(out + res)


class Model(nn.Module):
    supported_tasks = ['soft_sensor', 'process_monitoring', 'rul_estimation', 'fault_diagnosis', 'predictive_maintenance']

    def __init__(self, configs):
        super().__init__()
        self.task_name = configs.task_name
        self.seq_len = configs.seq_len
        self.pred_len = configs.seq_len

        layers = []
        num_channels = [self.pred_len] * configs.e_layers
        num_levels = len(num_channels)
        kernel_size = configs.moving_avg
        for i in range(num_levels):
            dilation_size = 2 ** i
            in_channels = self.seq_len if i == 0 else num_channels[i-1]
            out_channels = num_channels[i]
            layers += [
                TemporalBlock(
                    in_channels, out_channels, kernel_size, stride=1, dilation=dilation_size,
                    padding=(kernel_size-1) * dilation_size, dropout=configs.dropout
                )
            ]
        self.tcn = nn.Sequential(*layers)

        self.projection = OutputBlock(
            configs.enc_in, configs.c_out, seq_len=configs.seq_len, pred_len=configs.pred_len,
            task_name=self.task_name, dropout=configs.dropout
        )

    def encoder(self, x):
        # x shape: [B, L, D]
        x = self.tcn(x)
        return x

    def forward(self, x_enc, x_mark_enc, x_dec, x_mark_dec, mask=None):
        # Encoder
        enc_out = self.encoder(x_enc)
        # Output
        dec_out = self.projection(enc_out)
        return dec_out
