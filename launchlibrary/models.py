# Copyright 2018 Nir Harel
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
# limitations under the License.


from dateutil import parser
from dateutil import relativedelta
from functools import lru_cache
import datetime
from launchlibrary import Api

# Set default dt to the beginning of next month
DEFAULT_DT = datetime.datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0) \
             + relativedelta.relativedelta(months=1)


class BaseModel:
    """A class representing the base model of all models. Should be "private"."""

    def __init__(self, endpoint: str, param_translations: dict, nested_name: str, api_instance: Api, proper_name: str):
        # param translations serves both for pythonic translations and default param values
        self.param_translations = param_translations
        self.endpoint = endpoint
        self.nested_name = nested_name
        self.api_instance = api_instance
        self.proper_name = proper_name
        self.param_names = self.param_translations.keys()

    @classmethod
    def fetch(cls, api_instance: Api, **kwargs) -> list:
        """Initializes a class, or even a list of them from the api using the needed params."""
        cls_init = cls(api_instance)
        json_object = api_instance.send_message(cls_init.endpoint, kwargs)
        classes = []

        for entry in json_object.get(cls_init.nested_name, []):
            cls_init = cls(api_instance)
            cls_init.set_params_json(entry)
            cls_init.postprocess()
            classes.append(cls_init)

        return classes

    @classmethod
    def init_from_json(cls, api_instance: Api, json_object: dict):
        """
        Initializes a class from a json object. Only singular classes.
        :param api_instance: launchlibrary.Api
        :param json_object: An object containing the "entry" we want to init.
        :return: cls
        """
        cls_init = cls(api_instance)
        cls_init.set_params_json(json_object)
        cls_init.postprocess()
        return cls_init

    def set_params_json(self, json_object: dict):
        """Sets the parameters of a class from an object (raw data, not inside "agencies" for example)"""
        self.modelize(json_object)
        for pythonic_name, api_name in self.param_translations.items():
            setattr(self, pythonic_name, json_object.get(api_name, None))

    def modelize(self, json_object):
        """Recursively goes over the json object, looking for any compatible models. It'll be called again
        recursively, but in an indirect way."""
        for key, val in json_object.items():
            if key in MODEL_LIST_PLURAL.keys():
                if val:
                    if len(val) > 0:
                        json_object[key] = [MODEL_LIST_PLURAL[key].init_from_json(self.api_instance, r) for r in val]
            elif key in MODEL_LIST_SINGULAR.keys():  # if it is a singular
                if val:
                    if len(val) > 0:
                        json_object[key] = MODEL_LIST_SINGULAR[key].init_from_json(self.api_instance, val)

    def postprocess(self):
        """Optional method. May be used for model specific operations (like purging times)."""
        pass

    def __repr__(self) -> str:
        subclass_name = self.proper_name
        variables = ",".join(f"{k}={getattr(self, k)}" for k in self.param_translations.keys())

        return "{}({})".format(subclass_name, variables)


class AgencyType(BaseModel):
    def __init__(self, api_instance: Api):
        param_translations = dict(id="id", name="name", changed="changed")
        proper_name = self.__class__.__name__
        nested_name = "types"
        endpoint_name = "agencytype"

        super().__init__(endpoint_name, param_translations, nested_name, api_instance, proper_name)


class Agency(BaseModel):
    def __init__(self, api_instance: Api):
        param_translations = dict(id="id", name="name", abbrev="abbrev", type="type", country_code="countryCode"
                                  , wiki_url="wikiURL", info_urls="infoURLs", is_lsp="islsp", changed="changed")
        proper_name = self.__class__.__name__
        nested_name = "agencies"
        endpoint_name = "agency"

        super().__init__(endpoint_name, param_translations, nested_name, api_instance, proper_name)

    @lru_cache(maxsize=None)
    def get_type(self) -> AgencyType:
        """Returns the name of the agency type."""
        agency_type = AgencyType.fetch(self.api_instance, id=self.type)

        # To avoid attribute errors on the user's side, if the type is not found simply create an empty one.
        return agency_type[0] if len(agency_type) == 1 else AgencyType.init_from_json(self.api_instance, {})


class LaunchStatus(BaseModel):
    def __init__(self, api_instance: Api):
        param_translations = dict(id="id", name="name", description="description", changed="changed")
        proper_name = self.__class__.__name__
        nested_name = "types"
        endpoint_name = "launchstatus"

        super().__init__(endpoint_name, param_translations, nested_name, api_instance, proper_name)


class Launch(BaseModel):
    def __init__(self, api_instance: Api):
        self.datetime_conversions = dict()
        param_translations = dict(id="id", name="name", tbddate="tbddate", tbdtime="tbdtime", status="status"
                                  , inhold="inhold", windowstart="isostart", windowend="isoend",
                                  net="isonet", info_urls="infoURLs",
                                  vid_urls="vidURLs", holdreason="holdreason", failreason="failreason",
                                  probability="probability", hashtag="hashtag", _lsp="lsp", changed="changed",
                                  location="location", rocket="rocket", missions="missions")
        proper_name = self.__class__.__name__
        nested_name = "launches"
        endpoint_name = "launch"

        super().__init__(endpoint_name, param_translations, nested_name, api_instance, proper_name)

    @classmethod
    def next(cls, api_instance: Api, num: int) -> list:
        """
        A simple abstraction method to get the next {num} launches.
        :param api_instance: An instance of launchlibrary.Api
        :param num: a number for the number of launches
        """
        return cls.fetch(api_instance, next=num, status=1)

    @lru_cache(maxsize=None)
    def get_agency(self) -> Agency:
        """Gets the Agency model of the launch service provider either from json or from the server."""
        if self.api_instance.mode == "verbose" and self._lsp is not None:
            lsp = Agency.init_from_json(self.api_instance, self._lsp)
        else:
            lsp = Agency.fetch(self.api_instance, id=self._lsp)
            if len(lsp) > 0:
                lsp = lsp[0]

        return lsp

    @lru_cache(maxsize=None)
    def get_status(self) -> LaunchStatus:
        """Returns the LaunchStatus model for the corresponding status."""
        launch_status = LaunchStatus.fetch(self.api_instance, id=self.status)

        # To avoid attribute errors on the user's side, if the status is not found simply create an empty one.
        return launch_status[0] if len(launch_status) == 1 else LaunchStatus.init_from_json(self.api_instance, {})

    def postprocess(self):
        """Changes times to the datetime format."""
        for time_name in ["windowstart", "windowend", "net"]:
            try:
                # Will need to modify this if we ever implement modes other than verbose
                setattr(self, time_name, parser.parse(getattr(self, time_name, 0)))
            except ValueError:
                # The string might not contain a date, so we'll need to handle it with an empty datetime object.
                setattr(self, time_name, DEFAULT_DT)


class Pad(BaseModel):
    def __init__(self, api_instance: Api):
        param_translations = dict(id="id", name="name", pad_type="padType", latitude="latitude", longitude="longitude",
                                  map_url="mapURL", retired="retired", locationid="locationid", agencies="agencies",
                                  wiki_url="wikiURL", info_urls="infoURLs")
        proper_name = self.__class__.__name__
        nested_name = "pads"
        endpoint_name = "pad"

        super().__init__(endpoint_name, param_translations, nested_name, api_instance, proper_name)


class Location(BaseModel):
    def __init__(self, api_instance: Api):
        param_translations = dict(id="id", name="name", country_code="countrycode", wiki_url="wikiURL"
                                  , info_urls="infoURLs", pads="pads")  # pads might be included w/ launch endpoint
        proper_name = self.__class__.__name__
        nested_name = "pads"
        endpoint_name = "pad"

        super().__init__(endpoint_name, param_translations, nested_name, api_instance, proper_name)


MODEL_LIST_PLURAL = {"agencies": Agency, "pads": Pad, "locations": Location}  # putting it at the end to load the class
MODEL_LIST_SINGULAR = {"agency": Agency, "pad": Pad, "location": Location}
