"""
Classes and methods for constructing, evaluating, and doing parameter continuation of Hill Models

    Author: Shane Kepley
    email: shane.kepley@rutgers.edu
    Date: 2/29/20; Last revision: 3/4/20
"""
import numpy as np
import warnings
import matplotlib.pyplot as plt
from itertools import product, permutations
from scipy import optimize
from numpy import log
import textwrap


def npA(size):
    """Return a random numpy vector for testing"""
    return np.random.randint(1,10, 2*[size])


def is_vector(array):
    """Returns true if input is a numpy vector"""

    return len(np.shape(array)) == 1


def ezcat(*coordinates):
    """A multiple dispatch concatenation function for numpy arrays. Accepts arbitrary inputs as int, float, tuple,
    list, or numpy array and concatenates into a vector returned as a numpy array. This is recursive so probably not
    very efficient for large scale use."""

    if len(coordinates) == 1:
        if isinstance(coordinates[0], list):
            return np.array(coordinates[0])
        elif isinstance(coordinates[0], np.ndarray):
            return coordinates[0]
        else:
            return np.array([coordinates[0]])

    try:
        return np.concatenate([coordinates[0], ezcat(*coordinates[1:])])
    except ValueError:
        return np.concatenate([np.array([coordinates[0]]), ezcat(*coordinates[1:])])


def find_root(f, Df, initialGuess, diagnose=False):
    """Default root finding method to use if one is not specified"""

    solution = optimize.root(f, initialGuess, jac=Df, method='hybr')  # set root finding algorithm
    if diagnose:
        return solution  # return the entire solution object including iterations and diagnostics
    else:
        return solution.x  # return only the solution vector


def full_newton(f, Df, x0, maxDefect=1e-13):
    """A full Newton based root finding algorithm"""

    def is_singular(matrix, rank):
        """Returns true if the derivative becomes singular for any reason"""
        return np.isnan(matrix).any() or np.isinf(matrix).any() or np.linalg.matrix_rank(matrix) < rank

    fDim = len(x0)  # dimension of the domain/image of f
    maxIterate = 100

    if not is_vector(x0):  # an array whose columns are initial guesses
        print('not implemented yet')

    else:  # x0 is a single initial guess
        # initialize iteration
        x = x0.copy()
        y = f(x)
        Dy = Df(x)
        iDefect = np.linalg.norm(y)  # initialize defect
        iIterate = 1
        while iDefect > maxDefect and iIterate < maxIterate and not is_singular(Dy, fDim):
            if fDim == 1:
                x -= y / Dy
            else:
                x -= np.linalg.solve(Dy, y)  # update x

            y = f(x)  # update f(x)
            print(y)
            Dy = Df(x)  # update Df(x)
            iDefect = np.linalg.norm(y)  # initialize defect
            print(iDefect)
            iIterate += 1

        if iDefect < maxDefect:
            return x
        else:
            print('Newton failed to converge')
            return np.nan


def compose_interaction(interactionType, values):
    """Evaluate an interaction function of given type at the specified values.

    Input:
    interactionType: A partition of the integers {1,...,K} specified as an ordered list of integers which sum
        to exactly K. Example: [1,2,3] specifies the partition of {1,...,6} given by {1}, {2,3}, {4,5,6}
    values: A vector in R^K.
    Output:
    A vector of summands corresponding to the lists in the interactionType."""

    sumEndpoints = np.insert(np.cumsum(interactionType), 0,
                             0)  # summand endpoint indices including initial zero
    integerList = list(range(len(values)))  # list of integers [1,...,K]
    indicesBySummand = [integerList[sumEndpoints[idx]:sumEndpoints[idx + 1]] for idx in range(len(interactionType))]
    return np.array(list(map(lambda summandIndex: np.sum(values[summandIndex]), indicesBySummand)))


PARAMETER_NAMES = ['ell', 'delta', 'theta', 'hillCoefficient']  # ordered list of HillComponent parameter names


class HillComponent:
    """A component of a Hill system of the form ell + delta*H(x; ell, delta, theta, n) where H is an increasing or decreasing Hill function.
    Any of these parameters can be considered as a fixed value for a Component or included in the callable variables. The
    indices of the edges associated to ell, and delta are different than those associated to theta."""

    def __init__(self, interactionSign, **kwargs):
        """A Hill function with parameters [ell, delta, theta, n] of InteractionType in {-1, 1} to denote H^-, H^+ """
        # TODO: Class constructor should not do work!

        self.sign = interactionSign
        self.parameterValues = np.zeros(4)  # initialize vector of parameter values
        parameterNames = PARAMETER_NAMES.copy()  # ordered list of possible parameter names
        parameterCallIndex = {parameterNames[j]: j for j in range(4)}  # calling index for parameter by name
        for parameterName, parameterValue in kwargs.items():
            setattr(self, parameterName, parameterValue)  # fix input parameter
            self.parameterValues[
                parameterCallIndex[parameterName]] = parameterValue  # update fixed parameter value in evaluation vector
            del parameterCallIndex[parameterName]  # remove fixed parameter from callable list

        self.variableParameters = list(parameterCallIndex.keys())  # set callable parameters
        self.parameterCallIndex = list(parameterCallIndex.values())  # get indices for callable parameters
        self.fixedParameter = [parameterName for parameterName in parameterNames if
                               parameterName not in self.variableParameters]
        #  set callable parameter name functions
        for idx in range(len(self.variableParameters)):
            self.add_parameter_call(self.variableParameters[idx], idx)

    def __iter__(self):
        """Make iterable"""
        yield self

    def add_parameter_call(self, parameterName, parameterIndex):
        """Adds a call by name function for variable parameters to a HillComponent instance"""

        def call_function(self, parameter):
            """returns a class method which has the given parameter name. This method slices the given index out of a
            variable parameter vector"""
            return parameter[parameterIndex]

        setattr(HillComponent, parameterName, call_function)  # set dynamic method name

    def curry_parameters(self, parameter):
        """Returns a parameter evaluation vector in R^4 with fixed and variable parameters indexed properly"""
        parameterEvaluation = self.parameterValues.copy()  # get a mutable copy of the fixed parameter values
        parameterEvaluation[self.parameterCallIndex] = parameter  # slice passed parameter vector into callable slots
        return parameterEvaluation

    def __call__(self, x, parameter=np.array([])):
        """Evaluation method for a Hill component function instance"""

        # TODO: Handle the case that negative x values are passed into this function.

        ell, delta, theta, hillCoefficient = self.curry_parameters(
            parameter)  # unpack fixed and variable parameter values
        # compute powers of x and theta only once.
        xPower = x ** hillCoefficient
        thetaPower = theta ** hillCoefficient  # compute theta^hillCoefficient only once

        # evaluation rational part of the Hill function
        if self.sign == 1:
            evalRational = xPower / (xPower + thetaPower)
        elif self.sign == -1:
            evalRational = thetaPower / (xPower + thetaPower)
        return ell + delta * evalRational

    def __repr__(self):
        """Return a canonical string representation of a Hill component"""

        reprString = 'Hill Component: \n' + 'sign = {0} \n'.format(self.sign)
        for parameterName in PARAMETER_NAMES:
            if parameterName not in self.variableParameters:
                reprString += parameterName + ' = {0} \n'.format(getattr(self, parameterName))
        reprString += 'Variable Parameters: {' + ', '.join(self.variableParameters) + '}\n'
        return reprString

    def dx(self, x, parameter=np.array([])):
        """Evaluate the derivative of a Hill component with respect to x"""

        ell, delta, theta, hillCoefficient = self.curry_parameters(
            parameter)  # unpack fixed and variable parameter values
        # compute powers of x and theta only once.
        thetaPower = theta ** hillCoefficient
        xPowerSmall = x ** (hillCoefficient - 1)  # compute x^{hillCoefficient-1}
        xPower = xPowerSmall * x
        return self.sign * hillCoefficient * delta * thetaPower * xPowerSmall / ((thetaPower + xPower) ** 2)

    def dx2(self, x, parameter=np.array([])):
        """Evaluate the second derivative of a Hill component with respect to x"""

        ell, delta, theta, hillCoefficient = self.curry_parameters(
            parameter)  # unpack fixed and variable parameter values
        # compute powers of x and theta only once.
        thetaPower = theta ** hillCoefficient
        xPowerSmall = x ** (hillCoefficient - 2)  # compute x^{hillCoefficient-1}
        xPower = xPowerSmall * x ** 2
        return self.sign * hillCoefficient * delta * thetaPower * xPowerSmall * (
                (hillCoefficient - 1) * thetaPower - (hillCoefficient + 1) * xPower) / ((thetaPower + xPower) ** 3)

    def diff(self, x, parameter, diffIndex):
        """Evaluate the derivative of a Hill component with respect to a parameter at the specified local index.
        The parameter must be a variable parameter for the HillComponent."""

        diffParameter = self.variableParameters[diffIndex]  # get the name of the differentiation variable

        if diffParameter == 'ell':
            return 1.
        else:
            ell, delta, theta, hillCoefficient = self.curry_parameters(
                parameter)  # unpack fixed and variable parameters
            xPower = x ** hillCoefficient

        if diffParameter == 'delta':
            thetaPower = theta ** hillCoefficient  # compute theta^hillCoefficient only once
            if self.sign == 1:
                dH = xPower / (thetaPower + xPower) ** 2
            else:
                dH = thetaPower / (thetaPower + xPower) ** 2

        elif diffParameter == 'theta':
            thetaPowerSmall = theta ** (hillCoefficient - 1)  # compute power of theta only once
            thetaPower = theta * thetaPowerSmall
            dH = self.sign * (-delta * hillCoefficient * xPower * thetaPowerSmall) / ((thetaPower + xPower) ** 2)

        elif diffParameter == 'hillCoefficient':
            thetaPower = theta ** hillCoefficient
            dH = self.sign * delta * xPower * thetaPower * log(x / theta) / ((thetaPower + xPower) ** 2)

        return dH

    def diff2(self, diffIndex, x, parameter=np.array([])):
        """Evaluate the derivative of a Hill component with respect to a parameter at the specified local index.
        The parameter must be a variable parameter for the HillComponent."""

        # ordering of the variables decrease options
        if diffIndex[0] > diffIndex[1]:
            diffIndex = diffIndex[[1, 0]]

        diffParameter0 = self.variableParameters[diffIndex[0]]  # get the name of the differentiation variable
        diffParameter1 = self.variableParameters[diffIndex[1]]  # get the name of the differentiation variable

        if diffParameter0 == 'ell':
            return 0.
        else:
            ell, delta, theta, hillCoefficient = self.curry_parameters(
                parameter)  # unpack fixed and variable parameters

        # precompute some powers
        # this is the only power of x e will need
        xPower = x ** hillCoefficient
        # here we check which powers of theta we will need and compute them
        if diffParameter0 == 'theta' and diffParameter1 == 'theta':
            thetaPower_minusminus = theta ** (hillCoefficient - 2)
            thetaPower_minus = theta * thetaPower_minusminus  # compute power of theta only once
            thetaPower = theta * thetaPower_minus

        else:
            if diffParameter0 == 'theta' or diffParameter1 == 'theta':
                thetaPower_minus = theta ** (hillCoefficient - 1)  # compute power of theta only once
                thetaPower = theta * thetaPower_minus
            else:
                thetaPower = theta ** hillCoefficient

        if diffParameter0 == 'delta':
            if diffParameter1 == 'delta':
                return 0.
            if diffParameter1 == 'theta':
                dH = self.sign * -1 * hillCoefficient * xPower * thetaPower_minus / ((thetaPower + xPower) ** 2)
            if diffParameter1 == 'hillCoefficient':
                dH = self.sign * xPower * thetaPower * log(theta / x) / ((thetaPower + xPower) ** 2)

        elif diffParameter0 == 'theta':
            if diffParameter1 == 'theta':
                dH = self.sign * -delta * hillCoefficient * xPower * (thetaPower_minusminus * (hillCoefficient - 1) *
                                                                      (
                                                                              thetaPower + xPower) - thetaPower_minus * 2 * hillCoefficient *
                                                                      thetaPower_minus) / ((thetaPower + xPower) ** 3)
            if diffParameter1 == 'hillCoefficient':
                dH = - self.sign * delta * xPower * thetaPower_minus * \
                     ((1 + hillCoefficient * log(theta * x))(thetaPower + xPower)
                      - 2 * hillCoefficient * (log(theta) * thetaPower + log(x) * xPower)) \
                     / ((thetaPower + xPower) ** 3)
                # dH = self.sign * -delta * hillCoefficient * xPower * thetaPowerSmall / ((thetaPower + xPower) ** 2)

        elif diffParameter0 == 'hillCoefficient':
            # then diffParameter1 = 'hillCoefficient'
            dH = self.sign * delta / ((thetaPower + xPower) ** 4) * (
                    log(x * theta) * log(x / theta) * (thetaPower + xPower) ** 2 -
                    log(x / theta) * 2 * (thetaPower + xPower) * (thetaPower * log(theta) + xPower * log(x))
            )

        return dH

    def dxdiff(self, diffIndex, x, parameter=np.array([])):
        """Evaluate the derivative of a Hill component with respect to the state variable and a parameter at the specified
        local index.
        The parameter must be a variable parameter for the HillComponent."""

        diffParameter = self.variableParameters[diffIndex]  # get the name of the differentiation variable

        if diffParameter == 'ell':
            return 0.
        else:
            ell, delta, theta, hillCoefficient = self.curry_parameters(
                parameter)  # unpack fixed and variable parameters
            xPower = x ** hillCoefficient
            xPower_der = hillCoefficient * x ** (hillCoefficient - 1)

        if diffParameter == 'delta':
            thetaPower = theta ** hillCoefficient  # compute theta^hillCoefficient only once
            ddH = self.sign * hillCoefficient * thetaPower * xPower_der / (thetaPower + xPower) ** 3

        elif diffParameter == 'theta':
            thetaPowerSmall = theta ** (hillCoefficient - 1)  # compute power of theta only once
            thetaPower = theta * thetaPowerSmall
            dH = self.sign * (-delta * hillCoefficient * xPower * thetaPowerSmall) / ((thetaPower + xPower) ** 2)
            ddH = self.sign * delta * hillCoefficient ** 2 * thetaPowerSmall * xPower_der * \
                  (xPower - thetaPower) / (thetaPower + xPower) ** 3

        elif diffParameter == 'hillCoefficient':
            thetaPower = theta ** hillCoefficient
            dH = self.sign * delta * xPower * thetaPower * log(x / theta) / ((thetaPower + xPower) ** 2)
            ddH = self.sign * delta * thetaPower * xPower_der * (
                    (1 + hillCoefficient * log(x / theta)) * (xPower + thetaPower) - 2 * hillCoefficient * xPower * log(
                x / theta)
            ) / (thetaPower + xPower) ** 3

        return ddH

    def dx2diff(self, diffIndex, x, parameter=np.array([])):
        """Evaluate the derivative of a Hill component with respect to the state variable and a parameter at the specified
        local index.
        The parameter must be a variable parameter for the HillComponent."""

        diffParameter = self.variableParameters[diffIndex]  # get the name of the differentiation variable

        if diffParameter == 'ell':
            return 0.
        else:
            ell, delta, theta, hillCoefficient = self.curry_parameters(
                parameter)  # unpack fixed and variable parameters

        hill = hillCoefficient

        if diffParameter == 'delta':
            xPower_der = x ** (hillCoefficient - 1)
            xPower = x * xPower_der
            thetaPower = theta ** hillCoefficient  # compute theta^hillCoefficient only once
            d3H = self.sign * hillCoefficient * thetaPower * xPower_der * (
                    (hillCoefficient - 1) * thetaPower - (hillCoefficient + 1) * xPower) / ((thetaPower + xPower) ** 3)

        elif diffParameter == 'theta':
            xPower_derder = x ** (hillCoefficient - 2)
            xPower = x * xPower_derder * x
            x2Power = xPower * xPower
            thetaPower_der = theta ** (hillCoefficient - 1)  # compute power of theta only once
            thetaPower = theta * thetaPower_der
            theta2Power = thetaPower * thetaPower

            d3H = self.sign * hill ** 2 * delta * xPower_derder * thetaPower_der * \
                  (4 * hill * thetaPower * xPower + (-hill + 1) * theta2Power - (hill + 1) * x2Power) / (
                          (thetaPower + xPower) ** 4)

        elif diffParameter == 'hillCoefficient':
            xPower_derder = x ** (hillCoefficient - 2)
            xPower = x * xPower_derder * x
            x2Power = xPower * xPower

            thetaPower = theta ** hillCoefficient
            theta2Power = thetaPower * thetaPower

            d3H = self.sign * delta * (thetaPower * xPower_derder *
                                       ((thetaPower + xPower) * ((2 * hill - 1) * thetaPower - (2 * hill + 1) * xPower)
                                        - hill * ((hill - 1) * theta2Power - 4 * hill * thetaPower * xPower + (hill + 1)
                                                  * x2Power) * (log(theta) - log(x)))) / ((thetaPower + xPower) ** 4)

        return d3H

    def dxdiff2(self, diffIndex, x, parameter=np.array([])):
        """Evaluate the derivative of a Hill component with respect to a parameter at the specified local index.
        The parameter must be a variable parameter for the HillComponent."""

        # ordering of the variables decrease options
        if diffIndex[0] > diffIndex[1]:
            diffIndex = diffIndex[[1, 0]]

        diffParameter0 = self.variableParameters[diffIndex[0]]  # get the name of the differentiation variable
        diffParameter1 = self.variableParameters[diffIndex[1]]  # get the name of the differentiation variable

        if diffParameter0 == 'ell':
            return 0.
        else:
            ell, delta, theta, hillCoefficient = self.curry_parameters(
                parameter)  # unpack fixed and variable parameters

        hill = hillCoefficient

        # precompute some powers
        # this is the only power of x e will need
        xPower_minus = x ** (hill - 1)
        xPower = x * xPower_minus
        # here we check which powers of theta we will need and compute them
        if diffParameter0 == 'theta' and diffParameter1 == 'theta':
            thetaPower_minusminus = theta ** (hillCoefficient - 2)
            thetaPower_minus = theta * thetaPower_minusminus  # compute power of theta only once
            thetaPower = theta * thetaPower_minus

        else:
            if diffParameter0 == 'theta' or diffParameter1 == 'theta':
                thetaPower_minus = theta ** (hillCoefficient - 1)  # compute power of theta only once
                thetaPower = theta * thetaPower_minus
            else:
                thetaPower = theta ** hillCoefficient

        if diffParameter0 == 'delta':
            if diffParameter1 == 'delta':
                return 0.
            if diffParameter1 == 'theta':
                dH = self.sign * hill ** 2 * thetaPower_minus * xPower_minus * (xPower - thetaPower) / \
                     ((thetaPower + xPower) ** 3)
            if diffParameter1 == 'hillCoefficient':
                dH = self.sign * ((thetaPower * xPower_minus * (-hill * (thetaPower - xPower) * (log(theta) - log(x)) +
                                                                thetaPower + xPower))) / ((thetaPower + xPower) ** 3)

        elif diffParameter0 == 'theta':
            if diffParameter1 == 'theta':
                dH = (self.sign * delta * hill ** 2 * thetaPower_minusminus * xPower_minus * (
                        (hill + 1) * thetaPower ** 2
                        - 4 * hill * thetaPower * xPower + (hill - 1) * xPower ** 2)) / ((thetaPower + xPower) ** 4)
            if diffParameter1 == 'hillCoefficient':
                dH = - self.sign * (delta * hill * thetaPower_minus * xPower_minus * (-2 * thetaPower ** 2 +
                                                                                      hill * thetaPower ** 2 - 4 * thetaPower * xPower + xPower ** 2) *
                                    (log(theta) - log(x)) + 2 * xPower ** 2) / ((thetaPower + xPower) ^ 4)

        elif diffParameter0 == 'hillCoefficient':
            # then diffParameter1 = 'hillCoefficient'
            dH = self.sign * (delta * thetaPower * xPower_minus * (log(theta) - log(x)) * (-2 * thetaPower ** 2 + hill *
                                                                                           (
                                                                                                   thetaPower ** 2 - 4 * thetaPower * xPower + xPower ** 2) * (
                                                                                                   log(theta) - log(
                                                                                               x)) +
                                                                                           2 * xPower ** 2) / (
                                      (thetaPower + xPower) ** 4))

        return dH

    def dx3(self, x, parameter=np.array([])):
        """Evaluate the second derivative of a Hill component with respect to x"""

        ell, delta, theta, hillCoefficient = self.curry_parameters(
            parameter)  # unpack fixed and variable parameter values
        # compute powers of x and theta only once.
        hill = hillCoefficient
        thetaPower = theta ** hillCoefficient
        xPower_der3 = x ** (hill - 3)
        xPower_der2 = x * xPower_der3
        xPower_der = x * xPower_der2  # compute x^{hillCoefficient-1}
        xPower = xPower_der * x ** 2
        return self.sign(hill * delta * thetaPower * xPower_der3) / ((xPower + thetaPower) ** 4) * \
               ((-2 * (hill - 1) * xPower + (hill - 2) * thetaPower) * ((hill - 1) * thetaPower - (hill + 1) * xPower) -
                (hill + 1) * hill * xPower * (xPower + thetaPower))

    def dn(self, x, parameter=np.array([])):
        """Returns the derivative of a Hill component with respect to n. """

        ell, delta, theta, hillCoefficient = self.curry_parameters(
            parameter)  # unpack fixed and variable parameter values
        # compute powers of x and theta only once.
        xPower = x ** hillCoefficient
        thetaPower = theta ** hillCoefficient
        return self.sign * delta * xPower * thetaPower * log(x / theta) / ((thetaPower + xPower) ** 2)

    def dndx(self, x, parameter=np.array([])):
        """Returns the mixed partials of a Hill component with respect to n and x"""

        ell, delta, theta, hillCoefficient = self.curry_parameters(
            parameter)  # unpack fixed and variable parameter values
        # compute powers of x and theta only once.
        thetaPower = theta ** hillCoefficient
        xPowerSmall = x ** (hillCoefficient - 1)  # compute x^{hillCoefficient-1}
        xPower = xPowerSmall * x
        return self.sign * delta * thetaPower * xPowerSmall * (
                hillCoefficient * (thetaPower - xPower) * log(x / theta) + thetaPower + xPower) / (
                       (thetaPower + xPower) ** 3)

    def image(self, parameter=None):
        """Return the range of this HillComponent given by (ell, ell+delta)"""

        if 'ell' in self.variableParameters:
            ell = self.ell(parameter)
        else:
            ell = self.ell

        if 'delta' in self.variableParameters:
            delta = self.delta(parameter)
        else:
            delta = self.delta

        return np.array([ell, ell + delta])


class HillCoordinate:
    """Define a coordinate of the vector field for a Hill system as a function, f : R^K ---> R. If x does not have a nonlinear
     self interaction, then this is a scalar equation taking the form x' = -gamma*x + p(H_1, H_2,...,H_K) where each H_i is a Hill function depending on x_i which is a state variable
    which regulates x. Otherwise, it takes the form, x' = -gamma*x + p(H_1, H_2,...,H_K) where we write x_K = x. """

    def __init__(self, parameter, interactionSign, interactionType, interactionIndex, gamma=np.nan):
        """Hill Coordinate instantiation with the following syntax:
        INPUTS:
            gamma - (float) decay rate for this coordinate or NaN if gamma is a variable parameter which is callable as
                the first component of the parameter variable vector.
            parameter - (numpy array) A K-by-4 array of Hill component parameters with rows of the form [ell, delta, theta, hillCoefficient]
                Entries which are NaN are variable parameters which are callable in the function and all derivatives.
            interactionSign - (list) A vector in F_2^K carrying the sign type for each Hill component
            interactionType - (list) A vector describing the interaction type of the interaction function specified as an integer partition of K
            interactionIndex - (list) A length K+1 vector of global state variable indices. interactionIndex[0] is the global index
                for this coordinate and interactionIndex[1:] the indices of the K incoming interacting nodes"""

        # TODO: 1. Class constructor should not do work!
        #       2. Handing local vs global indexing of state variable vectors should be moved to the HillModel class instead of this class.
        #       3. There is a lot of redundancy between the "summand" methods and "component" methods. It is stil not clear how the code needs to be refactored.
        self.gammaIsVariable = np.isnan(gamma)
        if ~np.isnan(gamma):
            self.gamma = gamma  # set fixed linear decay
        self.parameterValues = parameter  # initialize array of fixed parameter values
        self.nComponent = len(interactionSign)  # number of interaction nodes
        self.components = self.set_components(parameter, interactionSign)
        self.index = interactionIndex[0]  # Define this coordinate's global index
        self.interactionIndex = interactionIndex[1:]  # Vector of global interaction variable indices
        self.interactionType = interactionType  # specified as an integer partition of K
        self.summand = self.set_summand()
        if self.nComponent == 1:  # Coordinate has a single HillComponent
            self.nVarByComponent = list(
                map(lambda j: np.count_nonzero(np.isnan(self.parameterValues)), range(self.nComponent)))
        else:  # Coordinate has multiple HillComponents
            self.nVarByComponent = list(
                map(lambda j: np.count_nonzero(np.isnan(self.parameterValues[j, :])), range(self.nComponent)))
        # endpoints for concatenated parameter vector by coordinate
        self.variableIndexByComponent = np.cumsum([self.gammaIsVariable] + self.nVarByComponent)
        # endpoints for concatenated parameter vector by coordinate. This is a
        # vector of length K+1. The kth component parameters are the slice variableIndexByComponent[k:k+1] for k = 0...K-1
        self.nVariableParameter = sum(
            self.nVarByComponent) + self.gammaIsVariable  # number of variable parameters for this coordinate.

    def parse_parameters(self, parameter):
        """Returns the value of gamma and slices of the parameter vector divided by component"""

        # If gamma is not fixed, then it must be the first coordinate of the parameter vector
        if self.gammaIsVariable:
            gamma = parameter[0]
        else:
            gamma = self.gamma
        return gamma, [parameter[self.variableIndexByComponent[j]:self.variableIndexByComponent[j + 1]] for
                       j in range(self.nComponent)]

    def __call__(self, x, parameter=np.array([])):
        """Evaluate the Hill coordinate on a vector of (global) state variables and (local) parameter variables. This is a
        map of the form  g: R^n x R^m ---> R where n is the number of state variables of the Hill model and m is the number
        of variable parameters for this Hill coordinate"""

        # TODO: Currently the input parameter must be a numpy array even if there is only a single parameter.
        if is_vector(x):  # Evaluate coordinate for a single x in R^n
            # slice callable parameters into a list of length K. The j^th list contains the variable parameters belonging to
            # the j^th Hill component.
            gamma, parameterByComponent = self.parse_parameters(parameter)
            hillComponentValues = self.evaluate_components(x, parameter)
            nonlinearTerm = self.interaction_function(hillComponentValues)  # compose with interaction function
            return -gamma * x[self.index] + nonlinearTerm

        # TODO: vectorized evaluation is a little bit hacky and should be rewritten to be more efficient
        else:  # vectorized evaluation where x is a matrix of column vectors to evaluate
            return np.array([self(x[:, j], parameter) for j in range(np.shape(x)[1])])

    def __repr__(self):
        """Return a canonical string representation of a Hill coordinate"""

        reprString = 'Hill Coordinate: {0} \n'.format(self.index) + 'Interaction Type: p = ' + (
                '(' + ')('.join(
            [' + '.join(['z_{0}'.format(idx + 1) for idx in summand]) for summand in self.summand]) + ')\n') + (
                             'Components: H = (' + ', '.join(
                         map(lambda i: 'H+' if i == 1 else 'H-', [H.sign for H in self.components])) + ') \n')

        # initialize index strings
        stateIndexString = 'State Variables: x = (x_{0}; '.format(self.index)
        variableIndexString = 'Variable Parameters: lambda = ('
        if self.gammaIsVariable:
            variableIndexString += 'gamma, '

        for k in range(self.nComponent):
            idx = self.interactionIndex[k]
            stateIndexString += 'x_{0}, '.format(idx)
            if self.components[k].variableParameters:
                variableIndexString += ', '.join(
                    [var + '_{0}'.format(idx) for var in self.components[k].variableParameters])
                variableIndexString += ', '

        # remove trailing commas and close brackets
        variableIndexString = variableIndexString[:-2]
        stateIndexString = stateIndexString[:-2]
        variableIndexString += ')\n'
        stateIndexString += ')\n'
        reprString += stateIndexString + '\n          '.join(textwrap.wrap(variableIndexString, 80))
        return reprString

    def evaluate_components(self, x, parameter):
        """Evaluate each HillComponent and return as a vector in R^K"""

        gamma, parameterByComponent = self.parse_parameters(parameter)
        return np.array(
            list(map(lambda H, idx, parm: H(x[idx], parm), self.components, self.interactionIndex,
                     parameterByComponent)))  # evaluate Hill components

    def summand_index(self, componentIdx):
        """Returns the summand index of a component index. This is a map of the form, I : {1,...,K} --> {1,...,q} which
        identifies to which summand the k^th component contributes."""

        return self.summand.index(filter(lambda L: componentIdx in L, self.summand).__next__())

    def evaluate_summand(self, x, parameter, m=None):
        """Evaluate the Hill summands at a given parameter. This is a map taking values in R^q. If m is given in arange(q)
        this returns only the m^th summand."""

        gamma, parameterByComponent = self.parse_parameters(parameter)

        if m is None:  # Return all summand evaluations as a vector in R^q
            return np.array(
                [self.evaluate_summand(x, parameter, m=summandIdx) for summandIdx in range(len(self.summand))])
        else:
            summand = self.summand[m]
            # parmBySummand = [parameterByComponent[k] for k in summand]
            # interactionIndex = [self.interactionIndex[k] for k in summand]
            componentValues = np.array(
                list(map(lambda k: self.components[k](x[self.interactionIndex[k]], parameterByComponent[k]),
                         summand)))  # evaluate Hill components
            return np.sum(componentValues)

    def interaction_function(self, componentValues):
        """Evaluate the polynomial interaction function at a parameter in (0,inf)^{K}"""

        if len(self.summand) == 1:  # this is the all sum interaction type
            return np.sum(componentValues)
        else:
            return np.prod([sum([componentValues[idx] for idx in summand]) for summand in self.summand])

    def diff_interaction(self, x, parameter, diffOrder, diffIndex=None):
        """Return the partial derivative of the specified order for interaction function in the coordinate specified by
        diffIndex. If diffIndex is not specified, it returns the full derivative as a vector with all K partials of
        order diffOrder."""

        # TODO: Fix the input to this function. It should accept the composition values as input, not evaluate them. This way it can be
        #       utilized for higher order derivatives as well by composing with the correct partial derivatives.

        def nonzero_index(order):
            """Return the indices for which the given order derivative of an interaction function is nonzero. This happens
            precisely for every multi-index in the tensor for which each component is drawn from a different summand."""

            summandTuples = permutations(self.summand, order)
            summandProducts = []  # initialize cartesian product of all summand tuples
            for tup in summandTuples:
                summandProducts += list(product(*tup))

            return np.array(summandProducts)

        nSummand = len(self.interactionType)  # number of summands
        if diffIndex is None:  # compute the full gradient of p with respect to all components

            if diffOrder == 1:  # compute first derivative of interaction function composed with Hill Components
                if nSummand == 1:  # the all sum special case
                    return np.ones(self.nComponent)
                else:
                    allSummands = self.evaluate_summand(x, parameter)
                    fullProduct = np.prod(allSummands)
                    DxProducts = fullProduct / allSummands  # evaluate all partials only once using q multiplies. The m^th term looks like P/p_m.
                    return np.array([DxProducts[self.summand_index(k)] for k in
                                     range(self.nComponent)])  # broadcast duplicate summand entries to all members

            elif diffOrder == 2:  # compute second derivative of interaction function composed with Hill Components as a 2-tensor
                if nSummand == 1:  # the all sum special case
                    return np.zeros(diffOrder * [self.nComponent])  # initialize Hessian of interaction function

                elif nSummand == 2:  # the 2 summands special case
                    DpH = np.zeros(diffOrder * [self.nComponent])  # initialize derivative tensor
                    idxArray = nonzero_index(diffOrder)  # array of nonzero indices for derivative tensor
                    DpH[idxArray[:, 0], idxArray[:, 1]] = 1  # set nonzero terms to 1
                    return DpH

                else:
                    DpH = np.zeros(2 * [self.nComponent])  # initialize Hessian of interaction function
                    # compute Hessian matrix of interaction function by summand membership
                    allSummands = self.evaluate_summand(x, parameter)
                    fullProduct = np.prod(allSummands)
                    DxProducts = fullProduct / allSummands  # evaluate all partials using only nSummand-many multiplies
                    DxxProducts = np.outer(DxProducts,
                                           1.0 / allSummands)  # evaluate all second partials using only nSummand-many additional multiplies.
                    # Only the cross-diagonal terms of this matrix are meaningful.
                    for row in range(nSummand):  # compute Hessian of interaction function (outside term of chain rule)
                        for col in range(row + 1, nSummand):
                            Irow = self.summand[row]
                            Icolumn = self.summand[col]
                            DpH[np.ix_(Irow, Icolumn)] = DpH[np.ix_(Icolumn, Irow)] = DxxProducts[row, col]

            elif diffOrder == 3:  # compute third derivative of interaction function composed with Hill Components as a 3-tensor
                if nSummand <= 2:  # the all sum or 2-summand special cases
                    return np.zeros(diffOrder * [self.nComponent])  # initialize Hessian of interaction function

                elif nSummand == 3:  # the 2 summands special case
                    DpH = np.zeros(diffOrder * [self.nComponent])  # initialize derivative tensor
                    idxArray = nonzero_index(diffOrder)  # array of nonzero indices for derivative tensor
                    DpH[idxArray[:, 0], idxArray[:, 1], idxArray[:, 2]] = 1  # set nonzero terms to 1
                    return DpH
                else:
                    raise KeyboardInterrupt

        else:  # compute a single partial derivative of p
            if diffOrder == 1:  # compute first partial derivatives
                if len(self.interactionType) == 1:
                    return 1.0
                else:
                    allSummands = self.evaluate_summand(x, parameter)
                    I_k = self.summand_index(diffIndex)  # get the summand index containing the k^th Hill component
                    return np.prod(
                        [allSummands[self.summand_index(diffIndex)] for m in range(self.nComponent) if
                         m != I_k])  # multiply over
                # all summands which do not contain the k^th component
            else:
                raise KeyboardInterrupt

    def dx(self, x, parameter, diffIndex=None):
        """Return the derivative as a gradient vector evaluated at x in R^n and p in R^m"""
        # TODO: The HillModel class should do the embedding into phase dimension (see dx2 for example).

        if diffIndex is None:
            gamma, parameterByComponent = self.parse_parameters(parameter)
            dim = len(x)  # dimension of vector field (Hill Model)
            # TODO: It is dangerous to allow the input to dictate the dimension. A better approach which allows exception handling is
            #   to write an intrinsic check of the dimension and ensure the input vector matches.
            Df = np.zeros(dim, dtype=float)
            xLocal = x[
                self.interactionIndex]  # extract only the coordinates of x that this HillCoordinate depends on as a vector in R^{K}
            diffInteraction = self.diff_interaction(x,
                                                    parameter,
                                                    1)  # evaluate derivative of interaction function (outer term in chain rule)
            DHillComponent = np.array(
                list(map(lambda H, x_k, parm: H.dx(x_k, parm), self.components, xLocal,
                         parameterByComponent)))  # evaluate vector of partial derivatives for Hill components (inner term in chain rule)
            Df[
                self.interactionIndex] = diffInteraction * DHillComponent  # evaluate gradient of nonlinear part via chain rule
            Df[self.index] -= gamma  # Add derivative of linear part to the gradient at this HillCoordinate
            return Df

        else:  # At some point we may need to call partial derivatives with respect to specific state variables by index
            return

    def diff(self, x, parameter, diffIndex=None):
        """Evaluate the derivative of a Hill coordinate with respect to a parameter at the specified local index.
           The parameter must be a variable parameter for one or more HillComponents."""

        # TODO: This function does not behave like dx. The phase space dimension embedding is not handled here. However,
        #       it still handles the projection. This job should be pushed to the HillModel class.  This should be
        #       changed at the same time as it is changed in the dx method.

        if diffIndex is None:  # return the full gradient with respect to parameters as a vector in R^m
            return np.array([self.diff(x, parameter, diffIndex=k) for k in range(self.nVariableParameter)])

        else:  # return a single partial derivative as a scalar
            if self.gammaIsVariable and diffIndex == 0:  # derivative with respect to decay parameter
                return -1
            else:  # First obtain a local index in the HillComponent for the differentiation variable
                diffComponent = np.searchsorted(self.variableIndexByComponent,
                                                diffIndex + 0.5) - 1  # get the component which contains the differentiation variable. Adding 0.5
                # makes the returned value consistent in the case that the diffIndex is an endpoint of the variable index list
                diffParameterIndex = diffIndex - self.variableIndexByComponent[
                    diffComponent]  # get the local parameter index in the HillComponent for the differentiation variable

                # Now evaluate the derivative through the HillComponent and embed into tangent space of R^n
                gamma, parameterByComponent = self.parse_parameters(parameter)
                xLocal = x[
                    self.interactionIndex]  # extract only the coordinates of x that this HillCoordinate depends on as a vector in R^{K}
                diffInteraction = self.diff_interaction(x, parameter, 1,
                                                        diffIndex=diffComponent)  # evaluate outer term in chain rule
                dpH = self.components[diffComponent].diff(xLocal[diffComponent],
                                                          parameterByComponent[
                                                              diffComponent], diffParameterIndex)  # evaluate inner term in chain rule
                return diffInteraction * dpH

    def dx2(self, x, parameter):
        """Return the second derivative (Hessian matrix) with respect to the state variable vector evaluated at x in
        R^n and p in R^m as a K-by-K matrix"""

        # TODO: This function does not behave like dx. The phase space dimension embedding is not handled here. However,
        #       it still handles the projection. This job should be pushed to the HillModel class.  This should be
        #       changed at the same time as it is changed in the dx method.

        gamma, parameterByComponent = self.parse_parameters(parameter)
        xLocal = x[
            self.interactionIndex]  # extract only the coordinates of x that this HillCoordinate depends on as a vector in R^{K}
        dim = len(list(
            set(self.interactionIndex + [self.index])))  # dimension of state vector input to HillCoordinate
        D2f = np.zeros(2*[dim])

        D2HillComponent = np.array(
            list(map(lambda H, x_k, parm: H.dx2(x_k, parm), self.components, xLocal, parameterByComponent)))
        # evaluate vector of second partial derivatives for Hill components
        nSummand = len(self.interactionType)  # number of summands

        if nSummand == 1:  # interaction is all sum
            D2Nonlinear = np.diag(D2HillComponent)
        # TODO: Adding more special cases for 2 and even 3 summand interaction types will speed up the computation quite a bit.
        #       This should be done if this method ever becomes a bottleneck.

        else:  # interaction function contributes derivative terms via chain rule

            # compute off diagonal terms in Hessian matrix by summand membership
            allSummands = self.evaluate_summand(x, parameter)
            fullProduct = np.prod(allSummands)
            DxProducts = fullProduct / allSummands  # evaluate all partials using only nSummand-many multiplies

            # initialize Hessian matrix and set diagonal terms
            DxProductsByComponent = np.array([DxProducts[self.summand_index(k)] for k in range(self.nComponent)])
            D2Nonlinear = np.diag(D2HillComponent * DxProductsByComponent)

            # set off diagonal terms of Hessian by summand membership and exploiting symmetry
            DxxProducts = np.outer(DxProducts,
                                   1.0 / allSummands)  # evaluate all second partials using only nSummand-many additional multiplies.
            # Only the cross-diagonal terms of this matrix are meaningful.

            offDiagonal = np.zeros_like(D2Nonlinear)  # initialize matrix of mixed partials (off diagonal terms)
            for row in range(nSummand):  # compute Hessian of interaction function (outside term of chain rule)
                for col in range(row + 1, nSummand):
                    offDiagonal[np.ix_(self.summand[row], self.summand[col])] = offDiagonal[
                        np.ix_(self.summand[col], self.summand[row])] = DxxProducts[row, col]

            DHillComponent = np.array(
                list(map(lambda H, x_k, parm: H.dx(x_k, parm), self.components, xLocal,
                         parameterByComponent)))  # evaluate vector of partial derivatives for Hill components
            mixedPartials = np.outer(DHillComponent,
                                     DHillComponent)  # mixed partial matrix is outer product of gradients!
            D2Nonlinear += offDiagonal * mixedPartials
            # NOTE: The diagonal terms of offDiagonal are identically zero for any interaction type which makes the
            # diagonal terms of mixedPartials irrelevant
        D2f[np.ix_(self.interactionIndex, self.interactionIndex)] = D2Nonlinear
        return D2f

    def dxdiff(self, x, parameter, diffIndex=None):
        """Return the mixed second derivative with respect to x and a scalar parameter evaluated at x in
        R^n and p in R^m as a gradient vector in R^K. If no parameter index is specified this returns the
        full second derivative as the m-by-K Hessian matrix of mixed partials"""

        # TODO: This function does not behave like dx. The phase space dimension embedding is not handled here. However,
        #       it still handles the projection. This job should be pushed to the HillModel class.  This should be
        #       changed at the same time as it is changed in the dx method.

        if diffIndex is None:
            return np.row_stack(list(map(lambda idx: self.dxdiff(x, parameter, idx), range(self.nVariableParameter))))

        else:
            gamma, parameterByComponent = self.parse_parameters(parameter)
            xLocal = x[
                self.interactionIndex]  # extract only the coordinates of x that this HillCoordinate depends on as a vector in R^{K}
            diffComponent = np.searchsorted(self.variableIndexByComponent,
                                            diffIndex + 0.5) - 1  # get the component which contains the differentiation variable. Adding 0.5
            # makes the returned value consistent in the case that the diffIndex is an endpoint of the variable index list
            diffParameterIndex = diffIndex - self.variableIndexByComponent[
                diffComponent]  # get the local parameter index in the HillComponent for the differentiation variable

            allSummands = self.evaluate_summand(x, parameter)
            I_k = self.summand_index(diffComponent)  # get the summand index containing the k^th Hill component

            Dxfp = self.dx(x,
                           parameter)  # initialize derivative of DxH with respect to differentiation parameter using the
            # full gradient vector of partials of H_k with respect to x in R^K

            # handle the I(j) != I(k) case
            Dxfp[self.summand[I_k]] = 0  # zero out all components satisfying I(j) = I(k)
            DpH = self.components[diffComponent].diff(diffParameterIndex, xLocal[diffComponent],
                                                      parameterByComponent[
                                                          diffComponent])  # evaluate partial derivative of H_k with respect to differentiation parameter
            Dxfp *= DpH / np.array([allSummands[self.summand_index(j)] for j in range(self.nComponent)])
            # scale by derivative of H_k with respect to differentiation parameter divided by p_I(j)

            # handle the j = k case
            DxHp = self.components[diffComponent].dxdiff(diffParameterIndex, xLocal[diffComponent],
                                                         parameterByComponent[
                                                             diffComponent])  # evaluate derivative of DxH_k with respect to differentiation parameter. This is a mixed second partial derivative.

            Dxfp[diffComponent] = DxHp * np.prod(
                [allSummands[self.summand_index(diffComponent)] for m in range(self.nComponent) if
                 m != I_k])  # multiply over
            # all summands which do not contain the k^th component
            return Dxfp

    def dx3(self, x, parameter):
        """Return the third derivative (3-tensor) with respect to the state variable vector evaluated at x in
        R^n and p in R^m as a K-by-K matrix"""

        # TODO: This function does not behave like dx. The phase space dimension embedding is not handled here. However,
        #       it still handles the projection. This job should be pushed to the HillModel class.  This should be
        #       changed at the same time as it is changed in the dx method.

        gamma, parameterByComponent = self.parse_parameters(parameter)
        xLocal = x[
            self.interactionIndex]  # extract only the coordinates of x that this HillCoordinate depends on as a vector in R^{K}

        # initialize all tensors for inner terms of chain rule derivatives of f
        DH = np.zeros(2 * [self.nComponent])
        D2H = np.zeros(3 * [self.nComponent])
        D3H = np.zeros(4 * [self.nComponent])

        # get vectors of appropriate partial derivatives of H
        DHillComponent = np.array(
            list(map(lambda H, x_k, parm: H.dx(x_k, parm), self.components, xLocal, parameterByComponent)))
        D2HillComponent = np.array(
            list(map(lambda H, x_k, parm: H.dx2(x_k, parm), self.components, xLocal, parameterByComponent)))
        D3HillComponent = np.array(
            list(map(lambda H, x_k, parm: H.dx3(x_k, parm), self.components, xLocal, parameterByComponent)))

        # set diagonal elements of inner derivative tensors to the correct partials
        np.einsum('ii->i', DH)[:] = DHillComponent
        np.einsum('iii->i', D2H)[:] = D2HillComponent
        np.einsum('iiii->i', D3H)[:] = D3HillComponent

        # get tensors for outer terms of chain rule derivatives of f
        Dp = self.diff_interaction(x, parameter, 1)  # 1-tensor
        D2p = self.diff_interaction(x, parameter, 2)  # 2-tensor
        D3p = self.diff_interaction(x, parameter, 3)  # 3-tensor

        # return D3f as a linear combination of tensor contractions via the chain rule
        D3f = np.einsum('ijl, jk', D3p, DH) + 2 * np.einsum('ij, jkl', D2p, D2H) + np.einsum('i,ijkl', Dp, D3H)
        return D3f

    def dx2diff(self, x, parameter):
        """Return the third derivative (3-tensor) with respect to the state variable vector (twice) and then the parameter
        (once) evaluated at x in R^n and p in R^m as a K-by-K matrix"""

        # TODO: This function does not behave like dx. The phase space dimension embedding is not handled here. However,
        #       it still handles the projection. This job should be pushed to the HillModel class.  This should be
        #       changed at the same time as it is changed in the dx method.

        gamma, parameterByComponent = self.parse_parameters(parameter)
        xLocal = x[
            self.interactionIndex]  # extract only the coordinates of x that this HillCoordinate depends on as a vector in R^{K}

        return

    def dxdiff2(self, x, parameter):
        """Return the third derivative (3-tensor) with respect to the state variable vector (once) and the parameters (twice)
        evaluated at x in R^n and p in R^m as a K-by-K matrix"""

        # TODO: This function does not behave like dx. The phase space dimension embedding is not handled here. However,
        #       it still handles the projection. This job should be pushed to the HillModel class.  This should be
        #       changed at the same time as it is changed in the dx method.

        gamma, parameterByComponent = self.parse_parameters(parameter)
        xLocal = x[
            self.interactionIndex]  # extract only the coordinates of x that this HillCoordinate depends on as a vector in R^{K}

        return

    def set_components(self, parameter, interactionSign):
        """Return a list of Hill components for this Hill coordinate"""

        def row2dict(row):
            """convert ordered row of parameter matrix to kwarg"""
            return {PARAMETER_NAMES[j]: row[j] for j in range(4) if
                    not np.isnan(row[j])}

        if self.nComponent == 1:
            return [HillComponent(interactionSign[0], **row2dict(parameter))]
        else:
            return [HillComponent(interactionSign[k], **row2dict(parameter[k, :])) for k in
                    range(self.nComponent)]  # list of Hill components

    def set_summand(self):
        """Return the list of lists containing the summand indices defined by the interaction type.
        EXAMPLE:
            interactionType = [2,1,3,1] returns the index partition [[0,1], [2], [3,4,5], [6]]"""

        sumEndpoints = np.insert(np.cumsum(self.interactionType), 0,
                                 0)  # summand endpoint indices including initial zero
        localIndex = list(range(self.nComponent))
        return [localIndex[sumEndpoints[i]:sumEndpoints[i + 1]] for i in range(len(self.interactionType))]

    def eq_interval(self, parameter=None):
        """Return a closed interval which must contain the projection of any equilibrium onto this coordinate"""

        if parameter is None:  # all parameters are fixed
            # TODO: This should only require all ell, delta, and gamma variables to be fixed.
            minInteraction = self.interaction_function([H.ell for H in self.components]) / self.gamma
            maxInteraction = self.interaction_function([H.ell + H.delta for H in self.components]) / self.gamma

        else:  # some variable parameters are passed in a vector containing all parameters for this Hill Coordinate
            gamma, parameterByComponent = self.parse_parameters(parameter)
            rectangle = np.row_stack(list(map(lambda H, parm: H.image(parm), self.components, parameterByComponent)))
            minInteraction = self.interaction_function(rectangle[:, 0]) / gamma  # min(f) = p(ell_1, ell_2,...,ell_K)
            maxInteraction = self.interaction_function(
                rectangle[:, 1]) / gamma  # max(f) = p(ell_1 + delta_1,...,ell_K + delta_K)
        return [minInteraction, maxInteraction]

    def dn(self, x, parameter=np.array([])):
        """Evaluate the derivative of a HillCoordinate with respect to the vector of Hill coefficients as a row vector.
        Evaluation requires specifying x in R^n and p in R^m. This method does not assume that all HillCoordinates have
        a uniform Hill coefficient. If this is the case then the scalar derivative with respect to the Hill coefficient
        should be the sum of the gradient vector returned"""

        warnings.warn(
            "The .dn method for HillComponents and HillCoordinates is deprecated. Use the .diff method instead.")
        gamma, parameterByComponent = self.parse_parameters(parameter)
        dim = len(x)  # dimension of vector field
        df_dn = np.zeros(dim, dtype=float)
        xLocal = x[
            self.interactionIndex]  # extract only the coordinates of x that this HillCoordinate depends on as a vector in R^{K}
        diffInteraction = self.diff_interaction(x, parameter, 1)  # evaluate outer term in chain rule
        dHillComponent_dn = np.array(
            list(map(lambda H, x, parm: H.dn(x, parm), self.components, xLocal,
                     parameterByComponent)))  # evaluate inner term in chain rule
        df_dn[
            self.interactionIndex] = diffInteraction * dHillComponent_dn  # evaluate gradient of nonlinear part via chain rule
        return df_dn


class HillModel:
    """Define a Hill model as a vector field describing the derivatives of all state variables. The i^th coordinate
    describes the derivative of the state variable, x_i, as a function of x_i and its incoming interactions, {X_1,...,X_{K_i}}.
    This function is always a linear decay and a nonlinear interaction defined by a polynomial composition of Hill
    functions evaluated at the interactions. The vector field is defined coordinate-wise as a vector of HillCoordinate instances"""

    def __init__(self, gamma, parameter, interactionSign, interactionType, interactionIndex):
        """Class constructor which has the following syntax:
        INPUTS:
            gamma - A vector in R^n of linear decay rates
            parameter - A length n list of K_i-by-4 parameter arrays
            interactionSign - A length n list of vectors in F_2^{K_i}
            interactionType - A length n list of length q_i lists describing an integer partitions of K_i
            interactionIndex - A length n list whose i^th element is a length K_i list of global indices for the i^th incoming interactions"""

        # TODO: Class constructor should not do work!
        # TODO? check if the interaction elements make sense together (i.e. they have the same dimensionality)

        self.dimension = len(gamma)  # Dimension of vector field i.e. n
        self.coordinates = [HillCoordinate(parameter[j], interactionSign[j],
                                           interactionType[j], [j] + interactionIndex[j], gamma=gamma[j]) for j in
                            range(self.dimension)]
        # A list of HillCoordinates specifying each coordinate of the vector field
        self.nVarByCoordinate = [fi.nVariableParameter for fi in
                                 self.coordinates]  # number of variable parameters by coordinate
        self.variableIndexByCoordinate = np.insert(np.cumsum(self.nVarByCoordinate), 0,
                                                   0)  # endpoints for concatenated parameter vector by coordinate
        self.nVariableParameter = sum(self.nVarByCoordinate)  # number of variable parameters for this HillModel

    def parse_parameter(self, *parameter):
        """Default parameter parsing if input is a single vector simply returns the same vector. Otherwise, it assumes
        input parameters are provided in order and concatenates into a single vector. This function is included in
        function calls so that subclasses can redefine function calls with customized parameters and overload this
        function as needed. Overloaded versions should take a variable number of numpy arrays as input and must always
        return a single numpy vector as output."""

        if parameter:
            return np.concatenate(parameter)
        else:
            return np.array([])

    def unpack_variable_parameters(self, parameter):
        """Unpack a parameter vector for the HillModel into component vectors for each distinct coordinate"""

        return [parameter[self.variableIndexByCoordinate[j]:self.variableIndexByCoordinate[j + 1]] for
                j in range(self.dimension)]

    def __call__(self, x, *parameter):
        """Evaluate the vector field defined by this HillModel instance. This is a function of the form
        f: R^n x R^{m_1} x ... x R^{m_n} ---> R^n where the j^th Hill coordinate has m_j variable parameters. The syntax
        is f(x,p) where p = (p_1,...,p_n) is a variable parameter vector constructed by ordered concatenation of vectors
        of the form p_j = (p_j1,...,p_jK) which is also an ordered concatenation of the variable parameters associated to
        the K-HillComponents for the j^th HillCoordinate."""

        parameter = self.parse_parameter(*parameter)  # concatenate all parameters into a vector
        parameterByCoordinate = self.unpack_variable_parameters(parameter)  # unpack variable parameters by component
        if is_vector(x):  # input a single vector in R^n
            return np.array(list(map(lambda f_i, parm: f_i(x, parm), self.coordinates, parameterByCoordinate)))
        else:  # vectorized input
            return np.row_stack(list(map(lambda f_i, parm: f_i(x, parm), self.coordinates, parameterByCoordinate)))

    def dx(self, x, *parameter):
        """Return the derivative (Jacobian) of the HillModel vector field with respect to x.
        NOTE: This function is not vectorized. It assumes x is a single vector in R^n."""

        parameter = self.parse_parameter(*parameter)  # concatenate all parameters into a vector
        parameterByCoordinate = self.unpack_variable_parameters(parameter)  # unpack variable parameters by component
        return np.vstack(list(map(lambda f_i, parm: f_i.dx(x, parm), self.coordinates,
                                  parameterByCoordinate)))  # return a vertical stack of gradient (row) vectors

    def dn(self, x, *parameter):
        """Return the derivative (Jacobian) of the HillModel vector field with respect to n assuming n is a VECTOR
        of Hill Coefficients. If n is uniform across all HillComponents, then the derivative is a gradient vector obtained
        by summing this Jacobian along rows.
        NOTE: This function is not vectorized. It assumes x is a single vector in R^n."""

        parameter = self.parse_parameter(*parameter)  # concatenate all parameters into a vector
        parameterByCoordinate = self.unpack_variable_parameters(parameter)  # unpack variable parameters by component
        return np.vstack(list(map(lambda f_i, parm: f_i.dn(x, parm), self.coordinates,
                                  parameterByCoordinate)))  # return a vertical stack of gradient (row) vectors

    def find_equilibria(self, gridDensity, *parameter, uniqueRootDigits=7):
        """Return equilibria for the Hill Model by uniformly sampling for initial conditions and iterating a Newton variant.
        INPUT:
            *parameter - (numpy vectors) Evaluations for variable parameters to use for evaluating the root finding algorithm
            gridDensity - (int) density to sample in each dimension.
            uniqueRootDigits - (int) Number of digits to use for distinguishing between floats."""

        # TODO: Include root finding method as kwarg

        # parameter = self.parse_parameter(*parameter)  # concatenate all parameters into a vector
        parameterByCoordinate = self.unpack_variable_parameters(
            self.parse_parameter(*parameter))  # unpack variable parameters by component

        def F(x):
            """Fix parameter values in the zero finding map"""
            return self.__call__(x, *parameter)

        def DF(x):
            """Fix parameter values in the zero finding map derivative"""
            return self.dx(x, *parameter)

        def eq_is_positive(equilibrium):
            """Return true if and only if an equlibrium is positive"""
            return np.all(equilibrium > 0)

        # build a grid of initial data for Newton algorithm
        coordinateIntervals = list(
            map(lambda f_i, parm: np.linspace(*f_i.eq_interval(parm), num=gridDensity), self.coordinates,
                parameterByCoordinate))
        evalGrid = np.meshgrid(*coordinateIntervals)
        X = np.row_stack([G_i.flatten() for G_i in evalGrid])
        solns = list(
            filter(lambda root: root.success and eq_is_positive(root.x), [find_root(F, DF, X[:, j], diagnose=True)
                                                                          for j in
                                                                          range(X.shape[
                                                                                    1])]))  # return equilibria which converged
        equilibria = np.column_stack([root.x for root in solns])  # extra equilibria as vectors in R^n
        equilibria = np.unique(np.round(equilibria, uniqueRootDigits), axis=1)  # remove duplicates
        return np.column_stack([find_root(F, DF, equilibria[:, j]) for j in
                                range(np.shape(equilibria)[1])])  # Iterate Newton again to regain lost digits


class ToggleSwitch(HillModel):
    """Two-dimensional toggle switch construction inherited as a HillModel where each node has free (but identical)
    Hill coefficients and possibly some other parameters free."""

    def __init__(self, gamma, parameter):
        """Class constructor which has the following syntax:
        INPUTS:
            gamma - A vector in R^n of linear decay rates
            parameter - A length n list of K_i-by-3 parameter arrays with rows of the form (ell, delta, theta)"""

        parameter = [np.insert(parmList, 3, np.nan) for parmList in
                     parameter]  # append hillCoefficient as free parameter
        interactionSigns = [[-1], [-1]]
        interactionTypes = [[1], [1]]
        interactionIndex = [[1], [0]]
        super().__init__(gamma, parameter, interactionSigns, interactionTypes,
                         interactionIndex)  # define HillModel for toggle switch
        self.hillIndexByCoordinate = self.variableIndexByCoordinate[1:] - np.array(range(1, 1 + self.dimension))

        # Define Hessian functions for HillCoordinates. This is temporary until the general formulas for the HillCoordinate
        # class is implemented.
        setattr(self.coordinates[0], 'dx2',
                lambda x, parm: np.array(
                    [[0, 0],
                     [0, self.coordinates[0].components[0].dx2(x[1], self.coordinates[0].parse_parameters(parm)[1])]]))
        setattr(self.coordinates[1], 'dx2',
                lambda x, parm: np.array(
                    [[self.coordinates[1].components[0].dx2(x[0], self.coordinates[1].parse_parameters(parm)[1]), 0],
                     [0, 0]]))

        setattr(self.coordinates[0], 'dndx',
                lambda x, parm: np.array(
                    [0, self.coordinates[0].components[0].dndx(x[1], self.coordinates[0].parse_parameters(parm)[1])]))
        setattr(self.coordinates[1], 'dndx',
                lambda x, parm: np.array(
                    [self.coordinates[1].components[0].dndx(x[0], self.coordinates[1].parse_parameters(parm)[1]), 0]))

    def parse_parameter(self, N, parameter):
        """Overload the parameter parsing for HillModels to identify all HillCoefficients as a single parameter, N. The
        parser Inserts copies of N into the appropriate Hill coefficient indices in the parameter vector."""

        return np.insert(parameter, self.hillIndexByCoordinate, N)

    def dn(self, x, N, parameter):
        """Overload the toggle switch derivative to identify the Hill coefficients which means summing over each
        gradient. This is a hacky fix and hopefully temporary. A correct implementation would just include a means to
        including the chain rule derivative of the hillCoefficient vector as a function of the form:
        Nvector = (N, N,...,N) in R^M."""

        Df_dHill = super().dn(x, N, parameter)  # Return Jacobian with respect to N = (N1, N2)  # OLD VERSION
        return np.sum(Df_dHill, 1)  # N1 = N2 = N so the derivative is tbe gradient vector of f with respect to N

    def plot_nullcline(self, n, parameter=np.array([]), nNodes=100, domainBounds=(10, 10)):
        """Plot the nullclines for the toggle switch at a given parameter"""

        equilibria = self.find_equilibria(25, n, parameter)
        Xp = np.linspace(0, domainBounds[0], nNodes)
        Yp = np.linspace(0, domainBounds[1], nNodes)
        Z = np.zeros_like(Xp)

        # unpack decay parameters separately
        gamma = np.array(list(map(lambda f_i, parm: f_i.parse_parameters(parm)[0], self.coordinates,
                                  self.unpack_variable_parameters(self.parse_parameter(n, parameter)))))
        N1 = (self(np.row_stack([Z, Yp]), n, parameter) / gamma[0])[0, :]  # f1 = 0 nullcline
        N2 = (self(np.row_stack([Xp, Z]), n, parameter) / gamma[1])[1, :]  # f2 = 0 nullcline

        if equilibria.ndim == 0:
            pass
        elif equilibria.ndim == 1:
            plt.scatter(equilibria[0], equilibria[1])
        else:
            plt.scatter(equilibria[0, :], equilibria[1, :])

        plt.plot(Xp, N2)
        plt.plot(N1, Yp)

# def unit_phase_condition(v):
#     """Evaluate defect for unit vector zero map of the form: U(v) = ||v|| - 1"""
#     return np.linalg.norm(v) - 1
#
#
# def diff_unit_phase_condition(v):
#     """Evaluate the derivative of the unit phase condition function"""
#     return v / np.linalg.norm(v)


# ## toggle switch plus
# # set some parameters to test
# decay = np.array([np.nan, np.nan], dtype=float)  # gamma
# f1parameter = np.array([[np.nan, np.nan, np.nan, np.nan] for j in range(2)], dtype=float)  # all variable parameters
# f2parameter = np.array([[np.nan, np.nan, np.nan, np.nan] for j in range(2)], dtype=float)  # all variable parameters
# parameter = [f1parameter, f2parameter]
# interactionSigns = [[1, -1], [1, -1]]
# interactionTypes = [[2], [2]]
# interactionIndex = [[0, 1], [1, 0]]
# tsPlus = HillModel(decay, parameter, interactionSigns, interactionTypes,
#                    interactionIndex)  # define HillModel for toggle switch plus
