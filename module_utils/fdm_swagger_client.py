from ansible.module_utils.six import integer_types, string_types

try:
    from ansible.module_utils.http import HTTPMethod
except (ImportError, ModuleNotFoundError):
    from module_utils.http import HTTPMethod

FILE_MODEL_NAME = '_File'
SUCCESS_RESPONSE_CODE = '200'


class PropName:
    ENUM = 'enum'
    TYPE = 'type'
    REQUIRED = 'required'
    INVALID_TYPE = 'invalid_type'
    REF = '$ref'
    ALL_OF = 'allOf'
    BASE_PATH = 'basePath'
    DEFINITIONS = 'definitions'
    OPERATIONS = 'operations'
    PATHS = 'paths'
    OPERATION_ID = 'operationId'
    PARAMETERS_FIELD = 'parameters'
    MODEL_NAME_FIELD = 'modelName'
    URL_FIELD = 'url'
    METHOD_FIELD = 'method'
    SCHEMA = 'schema'
    MODELS = 'models'
    ITEMS = 'items'
    PROPERTIES = 'properties'
    RESPONSES = 'responses'
    NAME = 'name'


class OperationParams:
    PATH = 'path'
    QUERY = 'query'


def _get_model_name_from_url(_schema_ref):
    path = _schema_ref.split('/')
    return path[len(path) - 1]


class FdmSwaggerParser:
    _definitions = None

    def parse_spec(self, spec):
        """
        This method simplifies a swagger format and also resolves a model name for each operation
        :param spec: expect data in the swagger format see <https://github.com/OAI/OpenAPI-Specification/blob/master/versions/2.0.md>
        :return:
            The models field contains model definition from swagger see <#https://github.com/OAI/OpenAPI-Specification/blob/master/versions/2.0.md#definitions>
            {
                'models':{
                    'model_name':{...},
                    ...
                },
                'operations':{
                    'operation_name':{
                        'method': 'get', #post, put, delete
                        'url': '/api/fdm/v2/object/networks', #url already contains a value from `basePath`
                        'modelName': 'NetworkObject', # it is a link to the model from 'models'
                                                      # None - for a delete operation or we don't have information
                                                      # '_File' - if an endpoint works with files
                        'parameters': {
                            'path':{
                                'param_name':{
                                    'type': 'string'#integer, boolean, number
                                    'required' True #False
                                }
                                ...
                                },
                            'query':{
                                'param_name':{
                                    'type': 'string'#integer, boolean, number
                                    'required' True #False
                                }
                                ...
                            }
                        }
                    }
                }
            }
        """
        self._definitions = spec[PropName.DEFINITIONS]
        config = {
            PropName.MODELS: self._definitions,
            PropName.OPERATIONS: self._get_operations(spec)
        }
        return config

    def _get_operations(self, spec):
        base_path = spec[PropName.BASE_PATH]
        paths_dict = spec[PropName.PATHS]
        operations_dict = {}
        for url, operation_params in paths_dict.items():
            for method, params in operation_params.items():
                operation = {
                    PropName.METHOD_FIELD: method,
                    PropName.URL_FIELD: base_path + url,
                    PropName.MODEL_NAME_FIELD: self._get_model_name(method, params)
                }
                if PropName.PARAMETERS_FIELD in params:
                    operation[PropName.PARAMETERS_FIELD] = self._get_rest_params(params[PropName.PARAMETERS_FIELD])

                operation_id = params[PropName.OPERATION_ID]
                operations_dict[operation_id] = operation
        return operations_dict

    def _get_model_name(self, method, params):
        if method == HTTPMethod.GET:
            return self._get_model_name_from_responses(params)
        elif method == HTTPMethod.POST or method == HTTPMethod.PUT:
            return self._get_model_name_for_post_put_requests(params)
        else:
            return None

    def _get_model_name_for_post_put_requests(self, params):
        model_name = None
        if PropName.PARAMETERS_FIELD in params:
            body_param_dict = self._get_body_param_from_parameters(params[PropName.PARAMETERS_FIELD])
            if body_param_dict:
                schema_ref = body_param_dict[PropName.SCHEMA][PropName.REF]
                model_name = self._get_model_name_by_schema_ref(schema_ref)
        if model_name is None:
            model_name = self._get_model_name_from_responses(params)
        return model_name

    @staticmethod
    def _get_body_param_from_parameters(params):
        return next((param for param in params if param['in'] == 'body'), None)

    def _get_model_name_from_responses(self, params):
        responses = params[PropName.RESPONSES]
        if SUCCESS_RESPONSE_CODE in responses:
            response = responses[SUCCESS_RESPONSE_CODE][PropName.SCHEMA]
            if PropName.REF in response:
                return self._get_model_name_by_schema_ref(response[PropName.REF])
            elif PropName.PROPERTIES in response:
                ref = response[PropName.PROPERTIES][PropName.ITEMS][PropName.ITEMS][PropName.REF]
                return self._get_model_name_by_schema_ref(ref)
            elif (PropName.TYPE in response) and response[PropName.TYPE] == "file":
                return FILE_MODEL_NAME
        else:
            return None

    def _get_rest_params(self, params):
        path = {}
        query = {}
        operation_param = {
            OperationParams.PATH: path,
            OperationParams.QUERY: query
        }
        for param in params:
            in_param = param['in']
            if in_param == OperationParams.QUERY:
                query[param[PropName.NAME]] = self._simplify_param_def(param)
            elif in_param == OperationParams.PATH:
                path[param[PropName.NAME]] = self._simplify_param_def(param)
        return operation_param

    @staticmethod
    def _simplify_param_def(param):
        return {
            PropName.TYPE: param[PropName.TYPE],
            PropName.REQUIRED: param[PropName.REQUIRED]
        }

    def _get_model_name_by_schema_ref(self, _schema_ref):
        model_name = _get_model_name_from_url(_schema_ref)
        model_def = self._definitions[model_name]
        if PropName.ALL_OF in model_def:
            return self._get_model_name_by_schema_ref(model_def[PropName.ALL_OF][0][PropName.REF])
        else:
            return model_name


class PropType:
    STRING = 'string'
    BOOLEAN = 'boolean'
    INTEGER = 'integer'
    NUMBER = 'number'
    OBJECT = 'object'
    ARRAY = 'array'


class FdmSwaggerValidator:
    def __init__(self, spec):
        """
        :param spec: data from FdmSwaggerParser().parse_spec()
        """
        self._operations = spec[PropName.OPERATIONS]
        self._models = spec[PropName.MODELS]

    def validate_data(self, operation_name, data=None):
        """
        Validate data for post|put requests
        :param operation_name: We use the operation name to get model specification
        :param data: data should be in the format that the model(from operation) expects
        :return:(Boolean, msg)
            (True, None) - if data valid
            Invalid:
            (False, 'The operation_name parameter must be a non-empty string' if operation_name - is not valid
            (False, 'The data parameter must be a dict' if data isn't dict or None
            (False, '{operation_name} operation does not support' - if the spec does not contain the operation
            (False, {
                'required': [ #list of the fields that are required but are not present in the data
                    'field_name',
                    'patent.field_name',# when the nested field is omitted
                    'patent.list[2].field_name' # if data is array and one of the field is omitted
                ],
                'invalid_type':[ #list of the fields with invalid data and expected type of the data
                        {
                           'path': 'objId', #field name or path to the field. Ex. objects[3].id, parent.name
                           'expected_type': 'string',# expected type. Ex. 'object', 'array', 'string', 'integer',
                                                     # 'boolean', 'number'
                           'actually_value': 1 # the value that user passed
                       }
                ]
            })
        """
        if data is None:
            data = {}

        if not operation_name or not isinstance(operation_name, string_types):
            return False, "The operation_name parameter must be a non-empty string"

        if not isinstance(data, dict):
            return False, "The data parameter must be a dict"

        if operation_name not in self._operations:
            return False, "{} operation does not support".format(operation_name)

        operation = self._operations[operation_name]
        model = self._models[operation['modelName']]
        status = self._init_report()

        self._validate_object(status, model, data, '')

        if len(status[PropName.REQUIRED]) > 0 or len(status[PropName.INVALID_TYPE]) > 0:
            return False, status
        return True, None

    def validate_query_params(self, operation_name, params):
        """
           Validate params for get requests in query part of the url.
           :param operation_name: We use the operation name to get specification for params
           :param params: data should be in the format that the specification expects
                    Ex.
                    {
                        'objId': "string_value",
                        'p_integer': 1,
                        'p_boolean': True,
                        'p_number': 2.3
                    }
           :return:(Boolean, msg)
               (True, None) - if params valid
               Invalid:
               (False, 'The operation_name parameter must be a non-empty string' if operation_name - is not valid
               (False, 'The params parameter must be a dict' if params isn't dict or None
               (False, '{operation_name} operation does not support' - if the spec does not contain the operation
               (False, {
                   'required': [ #list of the fields that are required but are not present in the params
                       'field_name'
                   ],
                   'invalid_type':[ #list of the fields with invalid data and expected type of the data
                            {
                              'path': 'objId', #field name
                              'expected_type': 'string',#expected type. Ex. 'string', 'integer', 'boolean', 'number'
                              'actually_value': 1 # the value that user passed
                            }
                   ]
               })
           """
        return self._validate_url_params(operation_name, params, resource=OperationParams.QUERY)

    def validate_path_params(self, operation_name, params):
        """
        Validate params for get requests in path part of the url.
        :param operation_name: We use the operation name to get specification for params
        :param params: data should be in the format that the specification expects
                 Ex.
                 {
                     'objId': "string_value",
                     'p_integer': 1,
                     'p_boolean': True,
                     'p_number': 2.3
                 }
        :return:(Boolean, msg)
            (True, None) - if params valid
            Invalid:
            (False, 'The operation_name parameter must be a non-empty string' if operation_name - is not valid
            (False, 'The params parameter must be a dict' if params isn't dict or None
            (False, '{operation_name} operation does not support' - if the spec does not contain the operation
            (False, {
                'required': [ #list of the fields that are required but are not present in the params
                    'field_name'
                ],
                'invalid_type':[ #list of the fields with invalid data and expected type of the data
                         {
                           'path': 'objId', #field name
                           'expected_type': 'string',#expected type. Ex. 'string', 'integer', 'boolean', 'number'
                           'actually_value': 1 # the value that user passed
                         }
                ]
            })
        """
        return self._validate_url_params(operation_name, params, resource=OperationParams.PATH)

    def _validate_url_params(self, operation, params, resource):
        if params is None:
            params = {}

        if not operation or not isinstance(operation, string_types):
            return False, "The operation_name parameter must be a non-empty string"

        if not isinstance(params, dict):
            return False, "The params parameter must be a dict"

        if operation not in self._operations:
            return False, "{} operation does not support".format(operation)

        operation = self._operations[operation]
        if PropName.PARAMETERS_FIELD in operation and resource in operation[PropName.PARAMETERS_FIELD]:
            spec = operation[PropName.PARAMETERS_FIELD][resource]
            status = self._init_report()
            self._check_url_params(status, spec, params)
            if len(status[PropName.REQUIRED]) > 0 or len(status[PropName.INVALID_TYPE]) > 0:
                return False, status
            return True, None
        else:
            return True, None

    def _check_url_params(self, status, spec, params):
        for prop_name in spec.keys():
            prop = spec[prop_name]
            if prop[PropName.REQUIRED] and prop_name not in params:
                status[PropName.REQUIRED].append(prop_name)
                continue
            if prop_name in params:
                expected_type = prop[PropName.TYPE]
                value = params[prop_name]
                if prop_name in params and not self._is_simple_types(expected_type, value):
                    self._add_invalid_type_report(status, '', prop_name, expected_type, value)

    def _validate_object(self, status, model, data, path):
        if self._is_enum(model):
            self._check_enum(status, model, data, path)
        elif self._is_object(model):
            self._check_object(status, model, data, path)

    def _is_enum(self, model):
        return self._is_string_type(model) and PropName.ENUM in model

    def _check_enum(self, status, model, value, path):
        if value not in model[PropName.ENUM]:
            self._add_invalid_type_report(status, path, '', PropName.ENUM, value)

    def _add_invalid_type_report(self, status, path, prop_name, expected_type, actually_value):
        status[PropName.INVALID_TYPE].append({
            'path': self._create_path_to_field(path, prop_name),
            'expected_type': expected_type,
            'actually_value': actually_value
        })

    def _check_object(self, status, model, data, path):
        if not isinstance(data, dict):
            self._add_invalid_type_report(status, path, '', PropType.OBJECT, data)
            return None

        self._check_required_fields(status, model[PropName.REQUIRED], data, path)

        model_properties = model[PropName.PROPERTIES]
        for prop in model_properties.keys():
            if prop in data:
                model_prop_val = model_properties[prop]
                expected_type = model_prop_val[PropName.TYPE]
                actually_value = data[prop]
                self._check_types(status, actually_value, expected_type, model_prop_val, path, prop)

    def _check_types(self, status, actually_value, expected_type, model, path, prop_name):
        if expected_type == PropType.OBJECT:
            ref_model = self._get_model_by_ref(model)

            self._validate_object(status, ref_model, actually_value,
                                  path=self._create_path_to_field(path, prop_name))
        elif expected_type == PropType.ARRAY:
            self._check_array(status, model, actually_value,
                              path=self._create_path_to_field(path, prop_name))
        elif not self._is_simple_types(expected_type, actually_value):
            self._add_invalid_type_report(status, path, prop_name, expected_type, actually_value)

    def _get_model_by_ref(self, model_prop_val):
        model = _get_model_name_from_url(model_prop_val['$ref'])
        return self._models[model]

    def _check_required_fields(self, status, required_fields, data, path):
        missed_required_fields = [self._create_path_to_field(path, field) for field in
                                  required_fields if field not in data.keys()]
        if len(missed_required_fields) > 0:
            status[PropName.REQUIRED] += missed_required_fields

    def _check_array(self, status, model, data, path):
        if not isinstance(data, list):
            self._add_invalid_type_report(status, path, '', PropType.ARRAY, data)
        else:
            item_model = model[PropName.ITEMS]
            for i, item_data in enumerate(data):
                self._check_types(status, item_data, item_model[PropName.TYPE], item_model, "{}[{}]".format(path, i),
                                  '')

    @staticmethod
    def _is_simple_types(expected_type, value):
        if expected_type == PropType.STRING:
            return isinstance(value, string_types)
        elif expected_type == PropType.BOOLEAN:
            return isinstance(value, bool)
        elif expected_type == PropType.INTEGER:
            return isinstance(value, integer_types) and not isinstance(value, bool)
        elif expected_type == PropType.NUMBER:
            return isinstance(value, (integer_types, float)) and not isinstance(value, bool)
        return False

    @staticmethod
    def _is_string_type(model):
        return PropName.TYPE in model and model[PropName.TYPE] == PropType.STRING

    @staticmethod
    def _init_report():
        return {
            PropName.REQUIRED: [],
            PropName.INVALID_TYPE: []
        }

    @staticmethod
    def _create_path_to_field(path='', field=''):
        separator = ''
        if path and field:
            separator = '.'
        return "{}{}{}".format(path, separator, field)

    @staticmethod
    def _is_object(model):
        return PropName.TYPE in model and model[PropName.TYPE] == PropType.OBJECT
