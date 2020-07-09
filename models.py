"""
A separate file to store important HillModel subclasses for analysis or testing

    Other files required: hill_model

    Author: Shane Kepley
    email: shane.kepley@rutgers.edu
    Date: 6/24/20; Last revision: 6/24/20
"""
from hill_model import *


class ToggleSwitch(HillModel):
    """Two-dimensional toggle switch construction inherited as a HillModel where each node has free (but identical)
    Hill coefficients, hill_1 = hill_2 = rho, and possibly some other parameters free. This is the simplest test case
    for analysis and also a canonical example of how to implement a HillModel in which some parameters are constrained
    by others."""

    def __init__(self, gamma, parameter):
        """Class constructor which has the following syntax:
        INPUTS:
            gamma - A vector in R^n of linear decay rates
            parameter - A length-2 list of length-3 parameter vectors of the form (ell, delta, theta)"""

        parameter = [np.insert(parmList, 3, np.nan) for parmList in
                     parameter]  # append hillCoefficient as free parameter
        interactionSigns = [[-1], [-1]]
        interactionTypes = [[1], [1]]
        interactionIndex = [[1], [0]]
        super().__init__(gamma, parameter, interactionSigns, interactionTypes,
                         interactionIndex)  # define HillModel for toggle switch by inheritance
        self.hillInsertionIndex = self.variableIndexByCoordinate[1:] - np.array(range(1, 1 + self.dimension))
        # insertion indices for HillCoefficients to expand the truncated parameter vector to a full parameter vector
        self.hillIndex = np.array(
            self.variableIndexByCoordinate[
            1:]) - 1  # indices of Hill coefficient parameters in the full parameter vector
        self.nonhillIndex = np.array([idx for idx in range(self.nVariableParameter) if
                                      idx not in self.hillIndex])  # indices of non Hill coefficient variable parameters in the full vector
        self.nVariableParameter -= 1  # adjust variable parameter count by 1 to account for the identified Hill coefficients.

    def parse_parameter(self, *parameter):
        """Overload the generic parameter parsing for HillModels to identify all HillCoefficients as a single parameter, rho. The
        parser Inserts copies of rho into the appropriate Hill coefficient indices in the parameter vector.

        INPUT: parameter is an arbitrary number of inputs which must concatenate to the ordered parameter vector with rho as first component.
            Example: parameter = (rho, p) with p in R^{m-2}
        OUTPUT: A vector of the form:
            lambda = (gamma_1, ell_1, delta_1, theta_1, rho, gamma_2, ell_2, delta_2, theta_2, rho),
        where any fixed parameters are omitted."""
        parameterVector = ezcat(
            *parameter)  # concatenate input into a single vector. Its first component must be the common hill parameter for both coordinates
        rho, p = parameterVector[0], parameterVector[1:]
        return np.insert(p, self.hillInsertionIndex, rho)

    def diff(self, x, *parameter, diffIndex=None):
        """Overload the diff function to identify the Hill parameters"""

        fullDf = super().diff(x, *parameter)
        Dpf = np.zeros([self.dimension, self.nVariableParameter])  # initialize full derivative w.r.t. all parameters
        Dpf[:, 1:] = fullDf[:, self.nonhillIndex]  # insert derivatives of non-hill parameters
        Dpf[:, 0] = np.einsum('ij->i',
                              fullDf[:, self.hillIndex])  # insert sum of derivatives for identified hill parameters

        if diffIndex is None:
            return Dpf  # return the full vector of partials
        else:
            return np.squeeze(Dpf[:, np.array([diffIndex])])  # return only columns for the specified subset of partials

    def dxdiff(self, x, *parameter, diffIndex=None):
        """Overload the dxdiff function to identify the Hill parameters"""

        fullDf = super().dxdiff(x, *parameter)
        Dpf = np.zeros(
            2 * [self.dimension] + [self.nVariableParameter])  # initialize full derivative w.r.t. all parameters
        Dpf[:, :, 1:] = fullDf[:, :, self.nonhillIndex]  # insert derivatives of non-hill parameters
        Dpf[:, :, 0] = np.einsum('ijk->ij', fullDf[:, :,
                                            self.hillIndex])  # insert sum of derivatives for identified hill parameters

        if diffIndex is None:
            return Dpf  # return the full vector of partials
        else:
            return np.squeeze(
                Dpf[:, :, np.array([diffIndex])])  # return only columns for the specified subset of partials

    def plot_nullcline(self, *parameter, nNodes=100, domainBounds=((0, 10), (0, 10))):
        """Plot the nullclines for the toggle switch at a given parameter"""

        X1, X2 = np.meshgrid(np.linspace(*domainBounds[0], nNodes), np.linspace(*domainBounds[1], nNodes))
        flattenNodes = np.array([np.ravel(X1), np.ravel(X2)])
        p1, p2 = self.unpack_variable_parameters(self.parse_parameter(*parameter))
        Z1 = np.reshape(self.coordinates[0](flattenNodes, p1), 2 * [nNodes])
        Z2 = np.reshape(self.coordinates[1](flattenNodes, p2), 2 * [nNodes])
        plt.contour(X1, X2, Z1, [0], colors='g')
        plt.contour(X1, X2, Z2, [0], colors='r')

    def plot_equilibria(self, *parameter, nInitData=10):
        """Find equilibria at given parameter and add to current plot"""

        equilibria = self.find_equilibria(nInitData, *parameter)
        if equilibria.ndim == 0:
            warnings.warn('No equilibria found')
            return
        elif equilibria.ndim == 1:
            plt.scatter(equilibria[0], equilibria[1])
        else:
            plt.scatter(equilibria[0, :], equilibria[1, :])
