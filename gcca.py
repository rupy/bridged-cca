#!/usr/bin/python
#-*- coding: utf-8 -*-

__author__ = 'rupy'

import numpy as np
from scipy.linalg import eig
import logging
import os
import matplotlib.pyplot as plt
import math
from matplotlib import colors
import h5py
from sklearn.datasets import load_digits

class GCCA:

    def __init__(self, n_components=2, reg_param=0.1):

        # log setting
        program = os.path.basename(__name__)
        self.logger = logging.getLogger(program)
        logging.basicConfig(format='%(asctime)s : %(name)s : %(levelname)s : %(message)s')

        # GCCA params
        self.n_components = n_components
        self.reg_param = reg_param

        # result of fitting
        self.data_num = 0
        self.cov_mat = [[]]
        self.h_list = []
        self.eigvals = np.array([])

        # result of transformation
        self.z_list = []

    def solve_eigprob(self, left, right):

        self.logger.info("calculating eigen dimension")
        eig_dim = min([np.linalg.matrix_rank(left), np.linalg.matrix_rank(right)])

        self.logger.info("calculating eigenvalues & eigenvector")
        eig_vals, eig_vecs = eig(left, right)

        self.logger.info("sorting eigenvalues & eigenvector")
        sort_indices = np.argsort(eig_vals)[::-1]
        eig_vals = eig_vals[sort_indices][:eig_dim].real
        eig_vecs = eig_vecs[:,sort_indices][:,:eig_dim].real

        # normalization
        self.logger.info("normalization")
        var = np.dot(eig_vecs.T, np.dot(right, eig_vecs))
        invvar = np.diag(np.reciprocal(np.sqrt(np.diag(var))))
        eig_vecs = np.dot(eig_vecs, invvar)

        return eig_vals, eig_vecs

    def calc_cov_mat(self, x_list):

        data_num = len(x_list)

        self.logger.info("calc variance & covariance matrix")
        z = np.vstack([x.T for x in x_list])
        cov = np.cov(z)
        d_list = [0] + [sum([len(x.T) for x in x_list][:i + 1]) for i in xrange(data_num)]
        cov_mat = [[np.array([]) for col in range(data_num)] for row in range(data_num)]
        for i in xrange(data_num):
            for j in xrange(data_num):
                i_start, i_end = d_list[i], d_list[i + 1]
                j_start, j_end = d_list[j], d_list[j + 1]
                cov_mat[i][j] = cov[i_start:i_end, j_start:j_end]

        return cov_mat

    def add_regularization_term(self, cov_mat):

        data_num = len(cov_mat)

        # regularization
        self.logger.info("adding regularization term")
        for i in xrange(data_num):
            cov_mat[i][i] += self.reg_param * np.average(np.diag(cov_mat[i][i])) * np.eye(cov_mat[i][i].shape[0])

        return cov_mat

    def fit(self, *x_list):

        # data size check
        data_num = len(x_list)
        self.logger.info("data num is %d", data_num)
        for i, x in enumerate(x_list):
            self.logger.info("data shape x_%d: %s", i, x.shape)

        self.logger.info("normalizing")
        x_norm_list = [ self.normalize(x) for x in x_list]

        d_list = [0] + [sum([len(x.T) for x in x_list][:i + 1]) for i in xrange(data_num)]
        cov_mat = self.calc_cov_mat(x_norm_list)
        cov_mat = self.add_regularization_term(cov_mat)

        self.logger.info("calculating generalized eigenvalue problem ( A*u = (lambda)*B*u )")
        # left = A, right = B
        left = 0.5 * np.vstack(
            [
                np.hstack([np.zeros_like(cov_mat[i][j]) if i == j else cov_mat[i][j] for j in xrange(data_num)])
                for i in xrange(data_num)
            ]
        )
        right = np.vstack(
            [
                np.hstack([np.zeros_like(cov_mat[i][j]) if i != j else cov_mat[i][j] for j in xrange(data_num)])
                for i in xrange(data_num)
            ]
        )

        # calc GEV
        self.logger.info("solving")
        eigvals, eigvecs = self.solve_eigprob(left, right)

        # substitute local variables for member variables
        self.data_num = data_num
        self.cov_mat = cov_mat
        self.h_list = [eigvecs[start:end] for start, end in zip(d_list[0:-1], d_list[1:])]
        self.eigvals = eigvals

    def transform(self, *x_list):

        # data size check
        data_num = len(x_list)
        self.logger.info("data num is %d", data_num)
        for i, x in enumerate(x_list):
            self.logger.info("data shape x_%d: %s", i, x.shape)

        if self.data_num != data_num:
            raise Exception('data num when fitting is different from data num to be transformed')

        self.logger.info("normalizing")
        x_norm_list = [ self.normalize(x) for x in x_list]

        self.logger.info("transform matrices by GCCA")
        z_list = [np.dot(x, h_vec) for x, h_vec in zip(x_norm_list, self.h_list)]

        self.z_list = z_list

        return z_list

    def fit_transform(self, *x_list):
        self.fit(x_list)
        self.transform(x_list)

    @staticmethod
    def normalize(mat):
        m = np.mean(mat, axis=0)
        mat = mat - m
        return mat

    def save_params(self, filepath):

        self.logger.info("saving gcca to %s", filepath)
        with h5py.File(filepath, 'w') as f:
            f.create_dataset("n_components", data=self.n_components)
            f.create_dataset("reg_param", data=self.reg_param)
            f.create_dataset("data_num", data=self.data_num)

            cov_grp = f.create_group("cov_mat")
            for i, row in enumerate(self.cov_mat):
                for j, cov in enumerate(row):
                    cov_grp.create_dataset(str(i) + "_" + str(j), data=cov)

            h_grp = f.create_group("h_list")
            for i, h in enumerate(self.h_list):
                h_grp.create_dataset(str(i), data=h)

            f.create_dataset("eig_vals", data=self.eigvals)

            if len(self.z_list) != 0:
                z_grp = f.create_group("z_list")
                for i, z in enumerate(self.z_list):
                    z_grp.create_dataset(str(i), data=z)
            f.flush()

    def load_params(self, filepath):
        self.logger.info("loading gcca from %s", filepath)
        with h5py.File(filepath, "r") as f:
            self.n_components = f["n_components"].value
            self.reg_param = f["reg_param"].value
            self.data_num = f["data_num"].value

            self.cov_mat = [[np.array([]) for col in range(self.data_num)] for row in range(self.data_num)]
            for i in xrange(self.data_num):
                for j in xrange(self.data_num):
                    self.cov_mat[i][j] = f["cov_mat/" + str(i) + "_" + str(j)]
            self.h_list = [None] * self.data_num
            for i in xrange(self.data_num):
                self.h_list[i] = f["h_list/" + str(i)].value
            self.eig_vals = f["eig_vals"].value

            if "z_list" in f:
                self.z_list = [None] * self.data_num
                for i in xrange(self.data_num):
                    self.z_list[i] = f["z_list/" + str(i)].value
            f.flush()

    def plot_gcca_result(self):

        self.logger.info("plotting gcca result")
        col_num = int(math.ceil(math.sqrt(self.data_num + 1)))
        row_num = int((self.data_num + 1) / float(col_num))
        if row_num != (self.data_num + 1) / float(col_num):
            row_num += 1

        # begin plot
        plt.figure()

        color_list = colors.cnames.keys()
        for i in xrange(self.data_num):

            plt.subplot(row_num, col_num, i + 1)
            plt.plot(self.z_list[i][:, 0], self.z_list[i][:, 1], c=color_list[i], marker='.', ls='-')
            plt.title("Z_%d(GCCA)" % (i + 1))

        plt.subplot(row_num, col_num, self.data_num + 1)
        for i in xrange(self.data_num):
            plt.plot(self.z_list[i][:, 0], self.z_list[i][:, 1], c=color_list[i], marker='.', ls='-')
            plt.title("Z_ALL(GCCA)")

        plt.show()

    def calc_correlations(self):
        for i, z_i in enumerate(self.z_list):
            for j, z_j in enumerate(self.z_list):
                if i < j:
                   print "(%d, %d): %f" % (i, j, np.corrcoef(z_i[:,0], z_j[:,0])[0, 1])


if __name__=="__main__":


    # set log level
    logging.root.setLevel(level=logging.INFO)

    # create data in advance
    # digit = load_digits()
    # a = digit.data[:100, 0::2]
    # b = digit.data[:100, 1::2]
    # c = digit.data[:100, 2::3]

    a = np.random.rand(50, 50)
    b = np.random.rand(50, 60)
    c = np.random.rand(50, 70)

    # create instance of GCCA
    gcca = GCCA(reg_param=0.001)
    # calculate GCCA
    gcca.fit(a, b)
    # transform
    gcca.transform(a, b)
    # save
    gcca.save_params("save/gcca.h5")
    # load
    gcca.load_params("save/gcca.h5")
    # plot
    gcca.plot_gcca_result()
    # calc correlations
    gcca.calc_correlations()
