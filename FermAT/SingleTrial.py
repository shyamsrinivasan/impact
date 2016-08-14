import numpy as np
import dill as pickle

import sqlite3 as sql

from .TrialIdentifier import TrialIdentifier
from .AnalyteData import TimeCourse


class SingleTrial(object):
    """
    Container for :class:`~TiterObject` to build a whole trial out of different measurements. E.g. one flask would
    contain data for biomass (OD), products (ethanol, acetate), substrates (glucose), fluorescence (gfpmut3, mCherry)
    """

    def __init__(self):
        self._t = np.array([])
        self.titerObjectDict = dict()
        self.trial_identifier = TrialIdentifier()
        self.yields = dict()

        self._substrate_name = None
        self.product_names = []
        self.biomass_name = None

        self.stage_indices = None
        self.stage_list = None

        self.normalized_data = dict()

    # Setters and Getters
    @property
    def stages(self):
        return self._stages

    @stages.setter
    def stages(self, stages):
        """
        Creates stages when they are defined

        Parameters
        ----------
        stages : list of stage start and end lists [start_index, end_index]

        """
        self._stages = stages

        for stage in stages:
            stage = self.create_stage(stage)
            self.stage_list.append(stage)

    @property
    def substrate_name(self):
        return self._substrate_name

    @substrate_name.setter
    def substrate_name(self, substrate_name):
        self._substrate_name = substrate_name
        self.check_time_vectors_match()
        self.calculate_substrate_consumed()
        if len(self.product_names) > 0:
            self.calculate_yield()

    @property
    def t(self):
        return self._t

    @t.setter
    def t(self, t):
        self._t = t

    @property
    def products(self):
        return self._products

    @products.setter
    def products(self, products):
        self._products = products
        if self._substrate:
            self.calculate_yield()

    def normalize_data(self, normalize_to):
        for product in self.product_names:
            self.normalized_data[product] = self.titerObjectDict[product] / self.titerObjectDict[normalize_to]

    def create_stage(self, stage_bounds):
        stage = SingleTrial()
        for titer in self.titerObjectDict:
            stage.add_titer(self.titerObjectDict[titer].create_stage(stage_bounds))
        stage.calculate_yield()

        return stage

    def db_commit(self, replicateID, c=None, stat=None):
        """
        Commit object to database.

        Parameters
        ----------
        replicateID : int
            replicateID to commit to
        c : sql cursor
        stat : str
            If this is a statistic (avg, std), which statistic? None is used for raw data.
        """
        if stat is None:
            stat_prefix = ''
        else:
            stat_prefix = '_' + stat

        c.execute(
            """INSERT INTO singleTrialTable""" + stat_prefix + """(replicateID, replicate_id, yieldsDict) VALUES (?, ?, ?)""",
            (replicateID, self.trial_identifier.replicate_id, pickle.dumps(self.yields)))

        c.execute("""SELECT MAX(singleTrialID""" + stat_prefix + """) from singleTrialTable""" + stat_prefix + """""")
        singleTrialID = c.fetchall()[0][0]

        for key in self.titerObjectDict:
            self.titerObjectDict[key].db_commit(singleTrialID, c=c, stat=stat)

    def db_load(self, singleTrialID=None, c=None, stat=None):
        """
        Load object from database.

        Parameters
        ----------
        singleTrialID : int
            The singleTrialID to laod
        c : SQL cursor
        stat : str
            If this is a statistic (avg, std), which statistic? None is used for raw data.

        Returns
        -------

        """
        c.execute("""SELECT yieldsDict FROM singleTrialTable WHERE singleTrialID == ?""", (singleTrialID,))
        data = c.fetchall()[0][0]
        self.yields = pickle.loads(data)

        if stat is None:
            stat_prefix = ''
        else:
            stat_prefix = '_' + stat

        c.execute(
            """SELECT yieldsDict FROM singleTrialTable""" + stat_prefix + """ WHERE singleTrialID""" + stat_prefix + """ == ?""",
            (singleTrialID,))
        temp = c.fetchall()

        data = temp[0][0]

        self.yields = pickle.loads(data)

        c.execute("""SELECT timeCourseID, singleTrial""" + stat_prefix + """ID, titerType, analyte_name, time_vector, data_vector, rate FROM
                timeCourseTable""" + stat_prefix + """ WHERE singleTrial""" + stat_prefix + """ID == ? """,
                  (singleTrialID,))
        for row in c.fetchall():
            # product = row[3]
            temp_titer_object = TimeCourse()
            for attribute in ['strain_id', 'id_1', 'id_2']:
                setattr(temp_titer_object.trial_identifier, attribute, getattr(self.trial_identifier, attribute))
            temp_titer_object.trial_identifier.id_1 = self.trial_identifier.id_1
            temp_titer_object.trial_identifier.identifier2 = self.trial_identifier.id_2
            temp_titer_object.trial_identifier.analyte_type = row[2]
            temp_titer_object.trial_identifier.analyte_name = row[3]

            if stat_prefix == '':
                temp_titer_object.trial_identifier.replicate_id = self.trial_identifier.replicate_id
                temp_titer_object._timeVec = np.loads(row[4])
            temp_titer_object._data_vector = np.loads(row[5])
            temp_titer_object.rate = pickle.loads(row[6])

            # self._t = self.titer_dict[product].time_vector
            self.add_titer(temp_titer_object)

        # The yields get recalculated when the titers are added, when in reality. A quick solution is to set the yield
        # to the correct values after adding all the titer objects (the std of the yield is not the ratio of the stds)
        self.yields = pickle.loads(data)

    def summary(self, print=False):
        summary = dict()
        summary['substrate'] = self._substrate_name
        summary['products'] = self.product_names
        summary['biomass'] = self.biomass_name
        summary['number_of_data_points'] = len(self._t)
        summary['run_identifier'] = self.trial_identifier.summary(['strain_id', 'id_1', 'id_2',
                                                                'replicate_id'])

        if print:
            print(summary)

        return summary

    def calculate_specific_productivity(self):
        """
        Calculate the specific productivity (dP/dt) given :math:`dP/dt = k_{Product} * X`
        """
        if self.biomass_name is None:
            return 'Biomass not defined'

        for product in self.product_names + [self.biomass_name] + [self.substrate_name]:
            self.titerObjectDict[product].specific_productivity = self.titerObjectDict[product].gradient / \
                                                                  self.titerObjectDict[self.biomass_name].data_vector

    def calculate_ODE_fit(self):
        """
        WIP to fit the data to ODEs
        """
        biomass = self.titerObjectDict[self.biomass_name].data_vector
        biomass_rate = np.gradient(self.titerObjectDict[self.biomass_name].data_vector) / np.gradient(
            self.titerObjectDict[self.biomass_name].time_vector)
        self.titerObjectDict[self.substrate_name]
        self.titerObjectDict[self.product_names]

        def dFBA_functions(y, t, rate):
            # Append biomass, substrate and products in one list
            exchange_reactions = biomass_flux + substrate_flux + product_flux
            # y[0]           y[1]
            dydt = []
            for exchange_reaction in exchange_reactions:
                if y[1] > 0:  # If there is substrate
                    dydt.append(exchange_reaction * y[0])
                else:  # If there is not substrate
                    dydt.append(0)
            return dydt

        import numpy as np
        from scipy.integrate import odeint

        # Let's assign the data to these variables
        biomass_flux = []
        biomass_flux.append(model.solution.x_dict[biomass_keys[0]])

        substrate_flux = []
        substrate_flux.append(model.solution.x_dict[substrate_keys[0]])

        product_flux = [model.solution.x_dict[key] for key in product_keys]

        exchange_keys = biomass_keys + substrate_keys + product_keys

        # Now, let's build our model for the dFBA
        def dFBA_functions(y, t, biomass_flux, substrate_flux, product_flux):
            # Append biomass, substrate and products in one list
            exchange_reactions = biomass_flux + substrate_flux + product_flux
            # y[0]           y[1]
            dydt = []
            for exchange_reaction in exchange_reactions:
                if y[1] > 0:  # If there is substrate
                    dydt.append(exchange_reaction * y[0])
                else:  # If there is not substrate
                    dydt.append(0)
            return dydt

        # Now let's generate the data
        sol = odeint(dFBA_functions, y0, t,
                     args=([flux * np.random.uniform(1 - noise, 1 + noise) for flux in biomass_flux],
                           [flux * np.random.uniform(1 - noise, 1 + noise) for flux in
                            substrate_flux],
                           [flux * np.random.uniform(1 - noise, 1 + noise) for flux in
                            product_flux]))

        dFBA_profile = {key: [row[i] for row in sol] for i, key in enumerate(exchange_keys)}

    def calculate_mass_balance(self, OD_gdw=None, calculateFBACO2=False):
        """
        Calculate a mass balance given the supplied substrate and products

        Parameters
        ----------
        OD_gdw : float
            The correlation betwen OD_gdw and OD600
        calculateFBACO2 : bool
            Flag to calculate the CO2 using FBA (not implemented yet)
        """
        # if calculateFBACO2:
        #     import cobra
        #
        #     # Load the COBRA model
        #     ...
        #
        #     # Convert the common names to COBRA model names
        #     commonNameCobraDictionary = {'Lactate'  : ...,
        #                                  'Ethanol'  : ...,
        #                                  'Acetate'  : ...,
        #                                  'Formate'  : ...,
        #                                  'Glycolate': ...,
        #                                  'Glucose'  : ...,
        #                                  'Succinate': ...
        #                                  }
        #
        #     # Get the molar mass from COBRA model and covert the grams to mmol
        #     substrate = model.metabolites.get_by_id(substrate_name)
        #     # substrate_mmol = substrate.formulaWeight()
        #     # substrate.lower_bound = self.substrate.data_vector[-1]
        #     # substrate.upper_bound = self.substrate.data_vector[-1]
        #     productsCOBRA = dict()
        #     for key in self.yields:
        #         modelMetID = commonNameCobraDictionary[key]
        #         productsCOBRA[key] = model.metabolites.get_by_id(modelMetID)
        #
        #     # Set the bounds
        #     ...
        #
        #     # Run the FBA and return the CO2
        #     ...

        if type(OD_gdw) == None:
            # Parameters for E. coli
            OD_gdw = 0.33  # Correlation for OD to gdw for mass balance

        # self.substrateConsumed

        if self.OD is not None:
            # Calc mass of biomass
            biomass_gdw = self._OD.data_vector / OD_gdw
        else:
            biomass_gdw = None

        # Calculate the mass of products consumed
        totalProductMass = np.sum([self.products[productKey].data_vector for productKey in self.products], axis=0)

        # Calculate the mass balance (input-output)
        if biomass_gdw is None:   biomass_gdw = np.zeros(
            [len(self.substrateConsumed)])  # If this isn't defined, set biomass to zero
        massBalance = self.substrateConsumed - totalProductMass - biomass_gdw

        return {'substrateConsumed': self.substrateConsumed,
                'totalProductMass' : totalProductMass,
                'biomass_gdw'      : biomass_gdw,
                'massBalance'      : massBalance}

    def add_titer(self, titerObject):
        """
        Add a :class:`~TiterObject`

        Parameters
        ----------
        titerObject : :class:`~TiterObject`
            A titer object to be added

        """

        # Check if this titer already exists
        if titerObject.trial_identifier.analyte_name in self.titerObjectDict:
            # print(self.biomass_name)
            # print(self.substrate_name)
            # print(self.product_names)
            # print(self.titer_dict.keys())
            raise Exception('A duplicate titer was added to the singleTiterObject,\n'
                            'Make sure replicates are defined properly,\n'
                            'Duplicate TrialIdentifier: ',
                            vars(titerObject.trial_identifier))

        self.titerObjectDict[titerObject.trial_identifier.analyte_name] = titerObject

        if titerObject.trial_identifier.analyte_type == 'substrate':
            if self.substrate_name is None:
                self.substrate_name = titerObject.trial_identifier.analyte_name
            else:
                raise Exception('No support for Multiple substrates: ', self.substrate_name, ' ',
                                titerObject.trial_identifier.analyte_name)
            self.calculate_substrate_consumed()

        if titerObject.trial_identifier.analyte_type == 'biomass' or titerObject.trial_identifier.analyte_type == 'OD':
            if self.biomass_name is None:
                self.biomass_name = titerObject.trial_identifier.analyte_name
            else:
                raise Exception('No support for Multiple biomasses: ', self.biomass_name, ' ',
                                titerObject.trial_identifier.analyte_name)

        if titerObject.trial_identifier.analyte_type == 'product':
            self.product_names.append(titerObject.trial_identifier.analyte_name)

            if self.substrate_name is not None:
                self.calculate_yield()

        # if 'substrate' in [self.titer_dict[key].trial_identifier.titerType for key in self.titer_dict] and \
        #                 'product' in [self.titer_dict[key].trial_identifier.titerType for key in
        #                               self.titer_dict]:
        #     self.calcYield()

        self.check_time_vectors_match()
        self.trial_identifier = titerObject.trial_identifier
        self.trial_identifier.time = None

    def check_time_vectors_match(self):
        """
        Ensure that the time vectors match between :class:`~AnalyteData` objects. Functionality to deal with missing data or
        data with different sizes is not implemented.
        """
        checkTimeVectorsFlag = 1
        if checkTimeVectorsFlag == 1:
            t = []
            flag = 0

            for key in self.titerObjectDict:
                t.append(self.titerObjectDict[key].time_vector)

            for i in range(len(t) - 1):
                if (t[i] != t[i + 1]).all():
                    index = i
                    flag = 1

            if flag == 1:
                raise (Exception(
                    "Time vectors within an experiment don't match, must implement new methods to deal with this type of data (if even possible)"))
            else:
                self._t = t[0]

    def get_unique_timepoint_id(self):
        return self.substrate.trial_identifier.strain_id + self.substrate.trial_identifier.id_1 + self.substrate.trial_identifier.identifier2 + str(
            self.substrate.trial_identifier.replicate_id)

    def get_unique_replicate_id(self):
        return self.titerObjectDict[list(self.titerObjectDict.keys())[0]].getReplicateID()

    def get_time(self, stage=None):
        if stage is not None:
            return self.t[self.stages[stage][0]:self.stages[stage][1]]
        else:
            return self.t

    def get_yields(self, stage=None):
        if stage is not None:
            self.calculate_substrate_consumed(stage=stage)
            self.calculate_yield(stage=stage)
            # print(stage)
            # print(self.yields)
            return self.yields
        else:
            return self.yields

    def calculate_substrate_consumed(self):
        stage = None
        if stage is None:
            self.substrateConsumed = np.array(
                [(self.titerObjectDict[self.substrate_name].data_vector[0] - dataPoint) for dataPoint in
                 self.titerObjectDict[self.substrate_name].data_vector])
        else:
            raise Exception('Unimplemented functionality')
            # print(self.substrate_name)
            # print(stage)
            # print(self.stages)
            self.substrateConsumed = np.array(
                [(self.titerObjectDict[self.substrate_name].data_vector[self.stages[stage][0]] - dataPoint) for dataPoint in
                 self.titerObjectDict[self.substrate_name].data_vector[self.stages[stage][0]:self.stages[stage][1]]])
            # print(self.substrateConsumed)
            # print(np.array(
            #     [(self.titer_dict[self.substrate_name].data_vector[0] - dataPoint) for dataPoint in
            #      self.titer_dict[self.substrate_name].data_vector]))

    def calculate_yield(self, stage=None):
        if stage is None:
            self.yields = dict()
            for productKey in [key for key in self.titerObjectDict if
                               self.titerObjectDict[key].trial_identifier.analyte_type == 'product']:
                try:
                    self.yields[productKey] = np.divide(
                        [(dataPoint - self.titerObjectDict[productKey].data_vector[0]) for dataPoint in
                         self.titerObjectDict[productKey].data_vector],
                        self.substrateConsumed)
                except Exception as e:
                    print(productKey)
                    print(self.titerObjectDict[productKey].data_vector)
                    print(e)
        else:
            raise Exception('Unimplemented functionality')
            self.yields = dict()
            for productKey in [key for key in self.titerObjectDict if
                               self.titerObjectDict[key].trial_identifier.analyte_type == 'product']:
                # print(self.stages)
                # print(stage)
                self.yields[productKey] = np.divide(
                    self.titerObjectDict[productKey].data_vector[self.stages[stage][0]:self.stages[stage][1]] -
                    self.titerObjectDict[productKey].data_vector[self.stages[stage][0]],
                    self.substrateConsumed
                )


class TimeCourseStage(TimeCourse):
    def __init__(self):
        TimeCourse().__init__()
        #
        # @TimeCourse.stage_indices.setter
        # def

        # class SingleTrialDataShell(SingleTrial):
        #     """
        #     Object which overwrites the SingleTrial objects setters and getters, acts as a shell of data with the
        #     same structure as SingleTrial
        #     """
        #
        #     def __init__(self):
        #         SingleTrial.__init__(self)
        #
        #     @SingleTrial.substrate.setter
        #     def substrate(self, substrate):
        #         self._substrate = substrate
        #
        #     @SingleTrial.OD.setter
        #     def OD(self, OD):
        #         self._OD = OD
        #
        #     @SingleTrial.products.setter
        #     def products(self, products):
        #         self._products = products