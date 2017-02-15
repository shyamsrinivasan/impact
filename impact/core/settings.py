from .secrets import *

import os.path
from ..database import Base

from sqlalchemy import Column, Boolean, Float, Integer

class Settings(Base):
    __tablename__ = 'settings'

    id = Column(Integer, primary_key=True)

    # general
    verbose = Column(Boolean)
    live_calculations = Column(Boolean)   # Perform calculation on the fly

    # database
    db_name = os.path.join(os.path.dirname(__file__), '../db/impact_db.sqlite3')

    # analyte_data
    remove_death_phase_flag = Column(Boolean)
    use_filtered_data = Column(Boolean)
    minimum_points_for_curve_fit = Column(Integer)
    savgolFilterWindowSize = Column(Integer)  # Must be odd
    perform_curve_fit = Column(Boolean)

    # replicate
    max_fraction_replicates_to_remove = Column(Float)
    default_outlier_cleaning_flag = Column(Boolean)
    outlier_cleaning_flag = Column(Boolean)

    def __init__(self):
        # general
        self.verbose = False
        self.live_calculations = False  # Perform calculation on the fly

        # database
        self.db_name = os.path.join(os.path.dirname(__file__), '../db/impact_db.sqlite3')

        # analyte_data
        self.remove_death_phase_flag = False
        self.use_filtered_data = False
        self.minimum_points_for_curve_fit = 5
        self.savgolFilterWindowSize = 21  # Must be odd
        self.perform_curve_fit = False

        # replicate
        self.max_fraction_replicates_to_remove = 0.5
        self.default_outlier_cleaning_flag = False
        self.outlier_cleaning_flag = False

settings = Settings()