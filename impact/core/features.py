import numpy as np

# Features
class MultiAnalyteFeature(object):
    """
    Base multi analyte feature. Use this to create new features.
    """
    def __init__(self):
        self.analyte_list = []
        self.name = ''

    @property
    def data(self):
        return 'Not implemented'

# class YieldTimePoint(object):
#     __tablename__ = 'yield_time_point'
#
#     id = Column(Integer, primary_key=True)
#     time = Column(Float)
#     data = Column(Float)



class ProductYield(MultiAnalyteFeature):
    def __init__(self, substrate, product):
        self.substrate = substrate
        self.product = product
        self.product_yield = None
        self.substrate_consumed = None

    @property
    def data(self):
        self.calculate()
        return self.product_yield

    def calculate(self):
        self.calculate_substrate_consumed()
        try:
            self.product_yield = np.divide(
                self.product.data_vector - np.tile(self.product.data_vector[0],[len(self.product.data_vector)]),
                self.substrate_consumed
            )
        except Exception as e:
            print(self.product)
            print(self.product.data_vector)
            raise Exception(e)

    def calculate_substrate_consumed(self):
        self.substrate_consumed = np.array(
            [(self.substrate.data_vector[0] - dataPoint)
             for dataPoint in self.substrate.data_vector]
        )

class ProductYieldFactory(object):
    requires = ['substrate','product', 'biomass']
    name = 'product_yield'

    def __init__(self):
        self.products = []
        self.substrate = None

    def add_analyte_data(self, analyte_data):
        if analyte_data.trial_identifier.analyte_type == 'substrate':
            if self.substrate is None:
                self.substrate = analyte_data

                if len(self.products) > 0:
                    for product in self.products:
                        product.product_yield = ProductYield(substrate=self.substrate, product=analyte_data)

                    # Once we've processed the waiting products we can delete them
                    self.product = []
            else:
                raise Exception('No support for Multiple substrates: ',
                                str(self.substrate.trial_identifier),
                                ' ',
                                str(analyte_data.trial_identifier))

        if analyte_data.trial_identifier.analyte_type in ['biomass','product']:
            if self.substrate is not None:
                analyte_data.product_yield = ProductYield(substrate=self.substrate, product=analyte_data)
            else:
                # Hold on to the product until a substrate is defined
                self.products.append(analyte_data)

class SpecificProductivityFactory(object):
    requires = ['substrate', 'product', 'biomass']
    name = 'specific_productivity'

    def __init__(self):
        self.biomass = None
        self.pending_analytes = []

    def add_analyte_data(self, analyte_data):
        if analyte_data.trial_identifier.analyte_type == 'biomass':
            self.biomass = analyte_data
            analyte_data.specific_productivity = SpecificProductivity(biomass=analyte_data,
                                                                              analyte=analyte_data)

            if len(self.pending_analytes) > 1:
                for analyte_data in self.pending_analytes:
                    analyte_data.specific_productivity = SpecificProductivity(biomass=self.biomass,
                                                                              analyte=analyte_data)

        if analyte_data.trial_identifier.analyte_type in ['substrate','product']:
            if self.biomass is not None:
                analyte_data.specific_productivity = SpecificProductivity(biomass=self.biomass, analyte=analyte_data)
            else:
                self.pending_analytes.append(analyte_data)

class SpecificProductivity(MultiAnalyteFeature):
    def __init__(self, biomass, analyte):
        self.biomass = biomass
        self.analyte = analyte
        self.specific_productivity = None

    @property
    def data(self):
        if self.specific_productivity is None:
            self.calculate()

        return self.specific_productivity

    def calculate(self):
        """
        Calculate the specific productivity (dP/dt) given :math:`dP/dt = k_{Product} * X`
        """
        if self.biomass is None:
            return 'Biomass not defined'

        try:
            if len(self.analyte.data_vector) > 2:
                self.analyte.calculate()    # Need gradient calculated before accessing
                self.specific_productivity = self.analyte.gradient / self.biomass.data_vector
        except Exception as e:
            print(self.analyte.data_vector)
            raise Exception(e)

class NormalizedData(MultiAnalyteFeature):
    def __init__(self, numerator, denominator):
        pass

class COBRAModelFactory(MultiAnalyteFeature):
    def __init__(self):
        self.requires = ['biomass','substrate','product']

    def calculate(self):
        import cameo
        iJO = cameo.models.iJO1366

class MassBalanceFactory(MultiAnalyteFeature):
    def __init__(self):
        self.requires = ['biomass','substrate','product']

class FeatureManager(object):
    def __init__(self):
        self.features = []
        self.analytes_to_features = {}
        self.analyte_types = ['biomass','substrate','product']
        for analyte_type in self.analyte_types:
            self.analytes_to_features[analyte_type] = []

    def register_feature(self, feature):
        self.features.append(feature)

        analyte_types = ['biomass','substrate','product']
        for analyte_type in analyte_types:
            if analyte_type in feature.requires:
                self.analytes_to_features[analyte_type].append(feature)
        setattr(self,feature.name,feature)

    def add_analyte(self, analyte_data):
        for analyte_type in self.analyte_types:
            for feature in self.features:
                if feature in self.analyte_types[analyte_type]:
                    feature.add_analyte(analyte_data)

# class TimeCourseStage(TimeCourse):
#     def __init__(self):
#         TimeCourse().__init__()
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