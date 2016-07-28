"""
        This file implements Batch Normalization as described in the paper:
        "Batch Normalization: Accelerating Deep Network Training
                              by Reducing Internal Covariate Shift"
                        by Sergey Ioffe, Christian Szegedy

        This implementation is useful for inputs NOT coming from convolution layers.
        For convolution layers, use nn.SpatialBatchNormalization.

        The operation implemented is:
        y =     ( x - mean(x) )
             ########## * gamma + beta
             standard-deviation(x)
        where gamma and beta are learnable parameters.

        The learning of gamma and beta is optional.

        Usage:
        with    learnable parameters: nn.BatchNormalization(N [, eps] [, momentum])
                                      where N = dimensionality of input
        without learnable parameters: nn.BatchNormalization(N [, eps] [, momentum], False)

        eps is a small value added to the standard-deviation to avoid divide-by-zero.
            Defaults to 1e-5

        In training time, this layer keeps a running estimate of it's computed mean and std.
        The running sum is kept with a default momentum of 0.1 (unless over-ridden)
        In test time, this running mean/std is used to normalize.
"""

import torch
from torch.legacy import nn

class BatchNormalization(nn.Module):
    # expected dimension of input

    def __init__(self, nOutput, eps=1e-5, momentum=0.1, affine=True):
        super(BatchNormalization, self).__init__()
        assert nOutput != 0

        self.affine = affine
        self.eps = eps
        self.train = True
        self.momentum = momentum
        self.running_mean = torch.zeros(nOutput)
        self.running_var = torch.ones(nOutput)

        self.save_mean = None
        self.save_std = None

        if self.affine:
           self.weight = torch.Tensor(nOutput)
           self.bias = torch.Tensor(nOutput)
           self.gradWeight = torch.Tensor(nOutput)
           self.gradBias = torch.Tensor(nOutput)
           self.reset()
        else:
           self.weight = None
           self.bias = None
           self.gradWeight = None
           self.gradBias = None

    def reset(self):
        if self.weight:
           self.weight.uniform()

        if self.bias:
           self.bias.zero()

        self.running_mean.zero()
        self.running_var.fill(1)

    def _checkInputDim(self, input):
        if input.dim() != 2:
            raise RuntimeError('only mini-batch supported (2D tensor), got {}D tensor instead'.format(input.dim()))
        if input.size(1) != self.running_mean.nElement():
            raise RuntimeError('got %d-feature tensor, expected %d'.format(input.size(1), self.running_mean.nElement()))

    def _makeContiguous(self, input, gradOutput=None):
        if not input.isContiguous():
            self._input = self._input or input.new()
            self._input.resizeAs(input).copy(input)
            input = self._input

        if gradOutput:
            if not gradOutput.isContiguous():
                self._gradOutput = self._gradOutput or gradOutput.new()
                self._gradOutput.resizeAs(gradOutput).copy(gradOutput)
                gradOutput = self._gradOutput

        return input, gradOutput

    def updateOutput(self, input):
        self._checkInputDim(input)

        input = self._makeContiguous(input)[0]

        self.output.resizeAs(input)
        self.save_mean = self.save_mean or input.new()
        self.save_mean.resizeAs(self.running_mean)
        self.save_std = self.save_std or input.new()
        self.save_std.resizeAs(self.running_var)

        self._backend.BatchNormalization_updateOutput(
            self._backend.library_state,
            input,
            self.output,
            self.weight,
            self.bias,
            self.running_mean,
            self.running_var,
            self.save_mean,
            self.save_std,
            self.train,
            self.momentum,
            self.eps
        )

        return self.output


    def _backward(self, input, gradOutput, scale, gradInput=None, gradWeight=None, gradBias=None):
        self._checkInputDim(input)
        self._checkInputDim(gradOutput)
        if not hasattr(self, 'save_mean') or not hasattr(self, 'save_std'):
            raise RuntimeError('you have to call updateOutput() at least once before backward()')

        input, gradOutput = self._makeContiguous(input, gradOutput)

        scale = scale or 1
        if gradInput is not None:
           gradInput.resizeAs(gradOutput)


        self._backend.BatchNormalization_backward(
            self._backend.library_state,
            input,
            gradOutput,
            gradInput,
            gradWeight,
            gradBias,
            self.weight,
            self.running_mean,
            self.running_var,
            self.save_mean,
            self.save_std,
            self.train,
            scale,
            self.eps
        )

        return self.gradInput

    def backward(self, input, gradOutput, scale=1):
        return self._backward(input, gradOutput, scale, self.gradInput, self.gradWeight, self.gradBias)

    def updateGradInput(self, input, gradOutput):
        return self._backward(input, gradOutput, 1, self.gradInput)

    def accGradParameters(self, input, gradOutput, scale=1):
        return self._backward(input, gradOutput, scale, None, self.gradWeight, self.gradBias)

    def read(self, file, version):
        super(BatchNormalization, self).read(self, file)
        if version < 2:
            if self.running_std:
                self.running_var = self.running_std.pow(-2).add(-self.eps)
                self.running_std = nil

    def clearState(self):
        # first 5 buffers are not present in the current implementation,
        # but we keep them for cleaning old saved models
        nn.utils.clear(self, {
           'buffer',
           'buffer2',
           'centered',
           'std',
           'normalized',
           '_input',
           '_gradOutput',
           'save_mean',
           'save_std',
        })
        return super(BatchNormalization, self).clearState()

