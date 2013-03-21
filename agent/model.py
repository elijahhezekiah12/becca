
import utils as ut
import numpy as np

class Model(object):

    def __init__(self, max_num_features, name):
        self.max_num_features = max_num_features
        self.name = name
        self.goal = np.zeros((max_num_features, 1))

        self.AGING_TIME_CONSTANT = 10 ** 6                  # real, large
        self.TRANSITION_UPDATE_RATE = 10 ** -1              # real, 0 < x < 1
        self.GOAL_DECAY_RATE = 0.1                          # real, 0 < x < 1
        self.INITIAL_UNCERTAINTY = 0.5                      # real, 0 < x < 1
        self.MATCH_EXPONENT = 4
        
        self.time_steps = 0
        model_shape = (max_num_features, max_num_features)        
        self.count = np.zeros(model_shape)
        self.reward_value = np.zeros(model_shape)
        self.reward_uncertainty = np.ones(model_shape) * self.INITIAL_UNCERTAINTY
        #self.goal_value = np.zeros(model_shape)

        state_shape = (max_num_features,1)
        self.new_cause = np.zeros(state_shape)
        self.new_effect = np.zeros(state_shape)
        self.num_feature_inputs = 0
             

    def update(self, feature_input, reward):        
        self.num_feature_inputs = np.maximum(self.num_feature_inputs, feature_input.size)
        # Pad the incoming feature_input array out to its full size if necessary 
        feature_input = ut.pad(feature_input, (self.max_num_features, 0))
        nonzero_feature_activities = np.nonzero(feature_input)[0]
        self.current_reward = reward
        self.CAUSE_DECAY_RATE = 0.33
        self.new_cause = ut.bounded_sum([self.new_effect, self.new_cause * (1 - self.CAUSE_DECAY_RATE)])
        self.new_effect = feature_input
        
        transition_activities = (self.new_cause * self.new_effect.T)  ** self.MATCH_EXPONENT
        update_rate_raw = transition_activities * ((1 - self.TRANSITION_UPDATE_RATE) / \
                    (self.count + ut.EPSILON) + self.TRANSITION_UPDATE_RATE)
        update_rate = np.minimum(0.5, update_rate_raw)
        
        reward_difference = np.abs(reward - self.reward_value)
        self.count += transition_activities
        self.count -=  np.minimum(1 / (self.AGING_TIME_CONSTANT * self.count + ut.EPSILON), self.count)
        self.reward_value += (reward - self.reward_value) * update_rate
        self.reward_uncertainty += (reward_difference - self.reward_uncertainty) * update_rate
        # Reshape transition activities into a single column
        return transition_activities.ravel()[:,np.newaxis]
   
    def deliberate(self, goal_value_by_transition):
        self.goal *= (1 - self.new_effect) * (1 - self.GOAL_DECAY_RATE)
        similarity = np.tile(self.new_effect, (1,self.new_effect.size))
        estimated_reward_value = self.reward_value + self.reward_uncertainty * \
                    (np.random.random_sample(self.reward_uncertainty.shape) * 2 - 1)
        estimated_reward_value = np.maximum(estimated_reward_value, 0)
        estimated_reward_value = np.minimum(estimated_reward_value, 1)
        reward_value_by_feature = ut.weighted_average(estimated_reward_value, 
                similarity / (self.reward_uncertainty + ut.EPSILON))
        
        #effect_jitter = ut.EPSILON * np.random.random_sample(self.effect.shape)
        
        """ Reshape goal_value_by_transition back into a square array """
        goal_value_by_transition = np.reshape(goal_value_by_transition, (self.goal.size, -1))

        """ Bounded sum of the goal values from above over all transitions """
        goal_value_by_feature = ut.bounded_sum(goal_value_by_transition.T * similarity)
        '''goal_value_by_transition = ut.map_inf_to_one(np.sum(ut.map_one_to_inf(
                            estimated_effect * (self.goal + goal_jitter)), axis=0)[np.newaxis,:])    
        goal_value_uncertainty_by_transition = ut.map_inf_to_one(np.sum(ut.map_one_to_inf(
                            self.effect_uncertainty * (self.goal + goal_jitter)), axis=0)[np.newaxis,:])
        goal_value_by_feature = ut.weighted_average(goal_value_by_transition, 
                context_matches * self.cause / (goal_value_uncertainty_by_transition + ut.EPSILON))
        '''
        '''goal_value_by_transition = np.tile(self.goal.T, (self.goal.size, 1))
        goal_value_by_feature = ut.weighted_average(goal_value_by_transition, similarity)
        '''
        count_by_feature = ut.weighted_average(self.count, similarity)
        exploration_vote = (1 - self.current_reward) / \
            (self.num_feature_inputs * (count_by_feature + 1) * 
             np.random.random_sample(count_by_feature.shape) + ut.EPSILON)
        exploration_vote = np.minimum(exploration_vote, 1.)
        exploration_vote[self.num_feature_inputs:] = 0.
        
        #total_vote = reward_value_by_feature + goal_value_by_feature + exploration_vote
        total_vote = reward_value_by_feature + exploration_vote
        
        adjusted_vote = total_vote * (1 - self.goal)
        new_goal_feature = np.argmax(adjusted_vote, axis=0)
        
        #bounded_total_vote = ut.bounded_sum([reward_value_by_feature, goal_value_by_feature, exploration_vote])
        bounded_total_vote = ut.bounded_sum([reward_value_by_feature, exploration_vote])
        
        self.goal[new_goal_feature, :] = np.maximum(bounded_total_vote[new_goal_feature, :], 
                                                    self.goal[new_goal_feature, :])
        return self.goal[:self.num_feature_inputs]

                 
    def get_projections(self, map_projections):
        num_inputs = self.reward_value.shape[0]
        all_causes = np.zeros((num_inputs,0))
        all_effects = np.zeros((num_inputs,0)) 
        for row in range(map_projections.shape[0]):
            transitions = np.reshape(map_projections[row,:], (num_inputs,num_inputs))
            cause = np.sign(np.max(transitions, axis=1))[:,np.newaxis]
            effect = np.sign(np.max(transitions, axis=0))[:,np.newaxis]
            all_causes = np.hstack((all_causes, cause))
            all_effects = np.hstack((all_effects, effect))
        return (all_causes, all_effects)
    
    def visualize(self, save_eps=True):
        import viz_utils
        viz_utils.visualize_array(self.reward_value, label=self.name + '_reward')
        #viz_utils.visualize_array(self.reward_uncertainty, label=self.name + '_reward_uncertainty')
        viz_utils.visualize_array(np.log(self.count + 1.), label=self.name + '_count')
        
        #viz_utils.visualize_model(self, self.num_primitives, self.num_actions, 10)
        return