
"""
The Text-Agent prompts a user for input, then sends the input to the UserAgent.

Interaction TBD.


Author: seantrott <seantrott@icsi.berkeley.edu>


------
See LICENSE.txt for licensing information.
------

"""

from nluas.core_agent import *
import json
import os
from collections import Counter

# Makes this work with both py2 and py3
from six.moves import input

class TextAgent(CoreAgent):
    def __init__(self, args):
        CoreAgent.__init__(self, args)
        self.clarification = False
        self.ui_destination = "{}_{}".format(self.federation, "AgentUI")
        self.text_address = "{}_{}".format(self.federation, "TextAgent")
        self.transport.subscribe(self.ui_destination, self.callback)
        # self.transport.subscribe(self.text_address, self.testing)
        self.original = None
        self.debug = True
        self.true_positive_intention = 0 # Number of intentions correctly classified
        self.true_negative_intention = 0 # Number of intentions correctly classified as Negative
        self.false_positive_intention = 0 # Number of intentions misclassified
        self.false_negative_intention = 0 # Number of intentions not classified

        # Full Command Recognition metrics
        self.true_positive_sentence = 0 # Number of sentences fully understood
        self.true_negative_sentence = 0 # Number of sentences correctly not recognized?
        self.false_positive_sentence = 0 # Number of sentences not fully understood
        self.false_negative_sentence = 0 # Number of sentences not recognized

        # Word Error Rate metrics
        self.actions_error_collection = []
        self.objects_error_collection = []
        self.people_error_collection = []
        self.locations_error_collection = []
        self.sentences_error_collection = []

        #-----Reseted after every sentence------


    def prompt(self):
        '''
        Creates a ntuple from the msg receives from the terminal
        '''
        msg = input("> ")

        if msg == "q":
            print("I am going to quit, BYE BYE") #NOTE ERICK
            self.close(True)
        elif msg == None or msg =="":
            pass
        else:
            if self.clarification:
                ntuple = {'text': msg, 'type': "clarification", 'original': self.original}
                # print("Prompt clarification: ", ntuple)
                self.clarification = False
            else:
                ntuple = {'text': msg, 'type': "standard"}
                # print("Prompt: ", ntuple)
            self.transport.send(self.ui_destination, ntuple)

    def send_message(self,phrase):
        '''
        Receive the phrase from the sentence analyzer and sends the phrase
        to the ecg model
        '''

        _ = input("\n-> Just press enter\n")

        # Get the phrase in the right format
        ntuple = {'text': phrase, 'type': "standard"}
        print("----> ntuple to send ", ntuple)
        # Send phrase to the ecg nlu model
        self.transport.send(self.ui_destination, ntuple)

    def sentence_analyzer(self,phrases, expected_output):
        '''
        Receive the phrases for each sentence in the dataset with the corresponding
        expected outputs (one per phrase)
        '''

        self.expected_output = expected_output #TODO Iterate per phrase

        if self.debug: print("The expected output is ", self.expected_output)

        self.n_phrases = len(phrases)
        print("Number of phrases in the sentence ", self.n_phrases)

        self.result = []
        self.phrase_counter = 0
        self.failed_counter = 0

        # Iterate over all the phrases to get the answer from the model
        for phrase in phrases:

            if phrase[-1] == ' ':
                phrase = phrase[:-1] + '!'
            else:
                phrase = phrase + '!'

            self.send_message(phrase)
            _ = input("-> Wait!\n")


    def callback(self, ntuple):
        """
        Callback for receiving information from User Agent.
        """
        # Error message obtained
        if ntuple == 'Failed':
            if self.debug: print("\033[1;31m Phrase not processed \033[0;37m")

            self.failed_counter += 1
            self.false_negative_intention += 1
            self.phrase_counter += 1
            self.result.append([])
            print('FN intention increased and empty list added to result')

            # print('phrase counter ', self.phrase_counter)
            # print('failed phrase counter ', self.failed_counter)

            if self.n_phrases == self.failed_counter:
                self.failed_counter = 0
                self.phrase_counter = 0
                if self.debug: print('\033[1;31m Sentence not processed\033[0;37m')
                self.false_negative_sentence += 1
                self.result = []

            if self.phrase_counter == self.n_phrases and len(list(filter(None, self.result))) != 0:
                self.failed_counter = 0
                self.phrase_counter = 0
                self.evaluate_output()
            return

        # if self.debug: print(ntuple)

        # Get the template of the semSpec
        try:
            template = ntuple['eventDescriptor']['eventProcess']['template']
        except:
            print('I got something weird\n')
            print(ntuple)

        if self.debug: print('----> Template ', template)

        if template == 'MotionPath':
            intent = 'go'
            goal = ntuple['eventDescriptor']['eventProcess']['spg']['spgDescriptor']['goal']['objectDescriptor']['type']
            msg = [[intent],[('destination', goal)]]

        elif template == 'ObjectTransfer':
            intent = 'take'
            object = ntuple['eventDescriptor']['eventProcess']['theme']['objectDescriptor']['type']
            # print('----> Action ', intent)
            # print('----> Object ', object)
            msg = [[intent],[('object', object)]]

        elif template == 'CauseEffect':
            actionary = ntuple['eventDescriptor']['eventProcess']['causalProcess']['actionary']
            print('Actionary ', actionary)
            if actionary == 'push':
                intent = 'push'
            else:
                intent = 'take'

            slots = []

            object = ntuple['eventDescriptor']['eventProcess']['causalProcess']['actedUpon']['objectDescriptor']['type']
            if object == 'sentient':
                object = 'it'
            slots.append(('object',object))
            try:
                source = ntuple['eventDescriptor']['eventProcess']['affectedProcess']['spg']['spgDescriptor']['source']['objectDescriptor']['type']
                slots.append(('source', source))
            except:
                pass

            try:
                goal = ntuple['eventDescriptor']['eventProcess']['affectedProcess']['spg']['spgDescriptor']['goal']['objectDescriptor']['type']
                if goal == 'person':
                    slots.append(('person', 'me'))
                else:
                    slots.append(('destination', goal))
            except:
                pass
            msg = [[intent],slots]

        elif template == 'Manipulation':
            object = ntuple['eventDescriptor']['eventProcess']['manipulated_entity']['objectDescriptor']['type']
            intent = 'take'
            # print('----> Action ', intent)
            # print('----> Object ', object)
            msg = [[intent],[('object', object)]]

        elif template == 'Perception':
            intent = 'find'
            object = ntuple['eventDescriptor']['eventProcess']['content']['objectDescriptor']['type']
            if object == 'person':
                name = ntuple['eventDescriptor']['eventProcess']['content']['objectDescriptor']['referent']
                msg = [[intent],[('person', name)]]
            else:
                msg = [[intent],[('object', object)]]

        else:
            print('------> Dumb!')
        # if debug: print('Output from ecg is ', msg)
        self.result.append(msg)

        self.phrase_counter += 1

        # print('Phrase counter ', self.phrase_counter)

        if self.phrase_counter == self.n_phrases:
            self.phrase_counter = 0
            self.evaluate_output()

    def evaluate_output(self):
        if self.debug: print('----> Output from ecg is ', self.result)

        passed_intentions = []
        passed_slots = []

        # Get the expected output and slot of sentence of each phrase
        for phrase_idx, expected_output in enumerate(self.expected_output):
            # Values extracted from the outputs file
            expected_intent = expected_output[0][0]
            expected_slots = expected_output[1]

            # Evaluates the intention
            try:
                assert self.result[phrase_idx][0][0] == expected_intent
                passed_intentions.append(True)
                self.true_positive_intention += 1
                print('TP intention increased')

            except:
                if self.debug: print("\033[1;31m ----> Intention failed \033[0;37m")

                # Check for empty intentions
                try:
                    # Check if intention was not classified correctly
                    _ = self.result[phrase_idx][0]
                    passed_intentions.append(False)
                    self.false_positive_intention += 1
                    print('FP intention increased')

                except IndexError:
                    # self.false_negative_intention += 1
                    # print('FN intention increased')
                    pass

                # self.actions_error_collection.append(expected_intent)

            # Evaluate the slots
            for slot_idx, slot in enumerate(expected_slots):

                try:
                    assert self.result[phrase_idx][1][slot_idx] == slot
                    passed_slots.append(True)

                except:
                    passed_slots.append(False)

                    # Switch case to add the error to the proper metric list
                    if slot[0] == 'object':
                        self.objects_error_collection.append(slot[1])

                    elif slot[0] == 'destination' or slot[0] == 'source':
                        self.locations_error_collection.append(slot[1])

                    elif slot[0] == 'person':
                        self.people_error_collection.append(slot[1])

                    elif slot[0] == 'sentence':
                        self.sentences_error_collection.append(slot[1])

                    else:
                        if self.debug: print('\033[1;31m ----> Slot not found \033[0;37m')
                        self.sentences_error_collection.append(slot[1])

        if all(passed_intentions) and all(passed_slots):
            self.true_positive_sentence += 1
            if self.debug: print("\033[1;36m Sentence passed! \033[0;37m")
            if self.debug: print('\033[1;32m--------------------------\033[0;37m')

        else:
            self.false_positive_sentence += 1
            if self.debug: print("\033[1;31m Sentence failed! \033[0;37m")
            if self.debug: print('\033[1;32m--------------------------\033[0;37m')

        # Reseting stuff
        self.result = []

    def compute_metrics(self):
        # Calculate the precision of the action detection TP / (TP + FP)
        ac_precision = self.true_positive_intention / (self.true_positive_intention + self.false_positive_intention)

        # Calculate the recall of the action detection TP / (TP + FN)
        ac_recall = self.true_positive_intention / (self.true_positive_intention + self.false_negative_intention)

        # Calculate the F-measure of the action detection (Precision * Recall) / (Precision + Recall)
        ac_f_measure = (ac_precision * ac_recall) / (ac_precision + ac_recall)

        # Calculate the accuracy of the recognition of the full command
        fcr_accuracy = (self.true_positive_sentence + self.true_negative_sentence) / (self.true_positive_sentence + \
                                                                            self.true_negative_intention + \
                                                                            self.false_positive_sentence + \
                                                                            self.false_negative_sentence)

        print('\033[1;32m==========================\033[0;37m')
        print('\033[1;32mTEST REPORT\033[0;37m')

        print('\033[1;32m==========================\033[0;37m')
        print('\033[1;34m AC & FCR METRICS \033[0;37m')
        print('\033[1;32m--------------------------\033[0;37m')
        print('\033[1;34m True positive intention is {} \033[0;37m'.format(self.true_positive_intention))
        print('\033[1;34m True negative intention is {} \033[0;37m'.format(self.true_negative_intention))

        print('\033[1;34m False positive intention is {} \033[0;37m'.format(self.false_positive_intention))
        print('\033[1;34m False negative intention is {} \033[0;37m'.format(self.false_negative_intention))

        print('\033[1;32m--------------------------\033[0;37m')

        print('\033[1;34m True positive sentence is {} \033[0;37m'.format(self.true_positive_sentence))
        print('\033[1;34m True negative sentence is {} \033[0;37m'.format(self.true_negative_sentence))

        print('\033[1;34m False positive sentece is {} \033[0;37m'.format(self.false_positive_sentence))
        print('\033[1;34m False negative sentece is {} \033[0;37m'.format(self.false_negative_sentence))

        print('\033[1;32m--------------------------\033[0;37m')
        print('\033[1;34m Action detection precision is {} \033[0;37m'.format(ac_precision))

        print('\033[1;34m Action detection recall is {} \033[0;37m'.format(ac_recall))

        print('\033[1;34m Action detection F-measure is {} \033[0;37m'.format(ac_f_measure))

        print('\033[1;32m--------------------------\033[0;37m')
        print('\033[1;34m Full Command Recognition accuracy is {} \033[0;37m'.format(fcr_accuracy))

        # print('\033[1;32m==========================\033[0;37m')
        # print('\033[1;34m WER METRICS \033[0;37m')
        # print('\033[1;32m--------------------------\033[0;37m')
        # print('\033[1;34m Actions error rate: {} \033[0;37m'.format(Counter(self.actions_error_collection)))
        # print('\033[1;34m Objects error rate: {} \033[0;37m'.format(Counter(self.objects_error_collection)))
        # print('\033[1;34m Locations error rate: {} \033[0;37m'.format(Counter(self.locations_error_collection)))
        # print('\033[1;34m People error rate: {} \033[0;37m'.format(Counter(self.people_error_collection)))
        # print('\033[1;34m Sentences error rate: {} \033[0;37m'.format(Counter(self.sentences_error_collection)))
        print('\033[1;32m==========================\033[0;37m')
        print('\033[1;32mTEST COMPLETE\033[0;37m')
        print('\033[1;32m==========================\033[0;37m')

    def output_stream(self, tag, message):
        print("TextAgent")
        print("{}: {}".format(tag, message))


if __name__ == "__main__":
    text = TextAgent(sys.argv[1:])
    text.keep_alive(text.prompt)
