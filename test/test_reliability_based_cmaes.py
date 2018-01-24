"""This module tests the reliability based CMAES learner."""
import unittest
import numpy as np

from pypuf.simulation.arbiter_based.ltfarray import LTFArray, NoisyLTFArray
from pypuf.learner.evolution_strategies.reliability_based_cmaes import ReliabilityBasedCMAES as Learner
from pypuf import tools


class TestReliabilityBasedCMAES(unittest.TestCase):
    """This class contains tests for the methods of the reliability based CMAES learner."""
    n = 16
    k = 2
    num = 2**12
    reps = 5
    mu_weight = 0
    sigma_weight = 1
    seed_instance = 0x1
    prng_i = np.random.RandomState(seed_instance)
    seed_model = 0x2
    prng_m = np.random.RandomState(seed_model)
    seed_challenges = 0x3
    prng_c = np.random.RandomState(seed_challenges)

    weight_array = np.array([
            [.1, .2, .3, .4, .5, .6, .7, .8, -.1, -.2, -.3, -.4, -.5, -.6, -.7, -.83],
            [.1, .2, .3, .4, -.5, -.6, -.7, -.8, -.1, -.2, -.3, -.4, .5, .6, .7, .81]
        ])
    sigma_noise = NoisyLTFArray.sigma_noise_from_random_weights(n, sigma_weight, noisiness=0.05)

    def setUp(self):
        self.transform = LTFArray.transform_id
        self.combiner = LTFArray.combiner_xor
        self.instance = NoisyLTFArray(self.weight_array, self.transform, self.combiner, self.sigma_noise, self.prng_i)
        self.training_set = tools.TrainingSet(self.instance, self.num, self.prng_c, self.reps)

    def test_create_fitness_function(self):
        measured_rels = Learner.measure_rels(self.training_set.responses)
        epsilon = .5
        fitness = Learner.create_fitness_function(
            challenges=self.training_set.challenges,
            measured_rels=measured_rels,
            epsilon=epsilon,
            transform=self.transform,
            combiner=self.combiner,
        )
        self.assertLessEqual(fitness(self.instance.weight_array[0, :]), 0.3)

    def test_create_abortion_function(self):
        is_same_solution = Learner.create_abortion_function(
            chains_learned=self.instance.weight_array,
            num_learned=2,
            transform=self.transform,
            combiner=self.combiner,
            threshold=0.25,
        )
        weight_array = np.array(
            [.8, .8, .8, .8, .5, .5, .5, .5, 1.4, 1.4, 1.4, 1.4, -.7, -.7, -.7, -.33]
        )
        self.assertFalse(is_same_solution(weight_array))
        self.assertTrue(is_same_solution(self.instance.weight_array[0, :]))

    def test_learn(self):
        pop_size = 12
        limit_stag = 100
        limit_iter = 1000
        logger = None
        learner = Learner(
            training_set=self.training_set,
            k=self.k,
            n=self.n,
            transform=self.transform,
            combiner=self.combiner,
            pop_size=pop_size,
            limit_stag=limit_stag,
            limit_iter=limit_iter,
            random_seed=self.seed_model,
            logger=logger,
        )
        model = learner.learn()
        distance = tools.approx_dist(self.instance, model, 10000)
        self.assertLessEqual(distance, 0.4)

    def test_calc_corr(self):
        rels_1 = np.array([0, 1, 2, 1])
        rels_2 = np.array([0, 0, 0, 1])
        rels_3 = np.array([0, 1, 2, 5])
        rels_4 = np.array([1, 1, 1, 1])
        corr_1_2 = Learner.calc_corr(rels_1, rels_2)
        corr_1_3 = Learner.calc_corr(rels_1, rels_3)
        corr_2_3 = Learner.calc_corr(rels_2, rels_3)
        corr_4_1 = Learner.calc_corr(rels_4, rels_1)
        self.assertLess(corr_1_2, corr_1_3)
        self.assertLess(corr_1_3, corr_2_3)
        self.assertEqual(corr_4_1, -1)

    def test_polarize_ltfs(self):
        learned_ltfs = np.array([
            [.5, -1, -.5, 1],
            [-1, -1, 1, 1],
        ])
        challenges = np.array(list(tools.sample_inputs(n=4, num=8, random_instance=self.prng_c)))
        majority_responses = np.array([1, 1, 1, 1, -1, -1, -1, -1])
        polarized_ltf_array = Learner.polarize_chains(
            chains_learned=learned_ltfs,
            challenges=challenges,
            majority_responses=majority_responses,
            transform=self.transform,
            combiner=self.combiner
        )
        self.assertIsNotNone(polarized_ltf_array)

    @unittest.skip
    def test_build_ltf_arrays(self):
        challenges = tools.sample_inputs(self.n, self.num)
        ltf_array_original = LTFArray(self.weight_array, self.transform, self.combiner)
        res_original = ltf_array_original.eval(challenges)
        weight_arrays = self.weight_array[np.newaxis, :].repeat(2, axis=0)
        ltf_arrays = Learner.build_ltf_arrays(weight_arrays, self.transform, self.combiner)
        for ltf_array in ltf_arrays:
            res = ltf_array.eval(challenges)
            np.testing.assert_array_equal(res, res_original)

    def test_build_individual_ltf_arrays(self):
        n = 16
        k = 2
        num = 2**10
        prng = np.random.RandomState(0x4)
        challenges = np.array(list(tools.sample_inputs(n, num, prng)))
        duplicated_weights = np.array([
            [.1, .2, .3, .4, .5, .6, .7, .8, -.1, -.2, -.3, -.4, -.5, -.6, -.7, -.8],
            [.1, .2, .3, .4, .5, .6, .7, .8, -.1, -.2, -.3, -.4, -.5, -.6, -.7, -.8]
        ])
        ltf_arrays = Learner.build_individual_ltf_arrays(duplicated_weights, self.transform, self.combiner)
        res = np.zeros((k, num))
        for i, ltf_array in enumerate(ltf_arrays):
            res[i, :] = ltf_array.eval(challenges)
        np.testing.assert_array_equal(res[0, :], res[1, :])

    responses = np.array([
        [1, 1, 1, 1],
        [1, 1, 1, -1],
        [1, 1, -1, -1],
        [1, -1, -1, -1]
    ])

    def test_common_responses(self):
        common_res = Learner.majority_responses(self.responses)
        self.assertEqual(common_res.all(), np.array([1, 1, 0, -1]).all())

    def test_measure_rels(self):
        rels = Learner.measure_rels(self.responses)
        self.assertEqual(rels.all(), np.array([4, 2, 0, 2]).all())
