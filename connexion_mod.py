import connexion.apis.flask_api as flask_api
import connexion.apps.flask_app as flask_app
import connexion.apps.abstract as abstract_app
import connexion.apis.flask_utils as flask_utils
import connexion.options as options_module
import connexion.resolver as resolver_module
import connexion.spec as spec_module
import copy
import flask
import logging
import pathlib
import sys
import urllib

logger = logging.getLogger(__name__)

class ListBlueprint(dict):
    pass

class NewFlaskApi(flask_api.FlaskApi):

    def __init__(self, specification, base_path=None, arguments=None,
                 validate_responses=False, strict_validation=False, resolver=None,
                 auth_all_paths=False, debug=False, resolver_error_handler=None,
                 validator_map=None, pythonic_params=False, pass_context_arg_name=None, options=None,
                 ):
        """
        :type specification: pathlib.Path | dict
        :type base_path: str | None
        :type arguments: dict | None
        :type validate_responses: bool
        :type strict_validation: bool
        :type auth_all_paths: bool
        :type debug: bool
        :param validator_map: Custom validators for the types "parameter", "body" and "response".
        :type validator_map: dict
        :param resolver: Callable that maps operationID to a function
        :param resolver_error_handler: If given, a callable that generates an
            Operation used for handling ResolveErrors
        :type resolver_error_handler: callable | None
        :param pythonic_params: When True CamelCase parameters are converted to snake_case and an underscore is appended
            to any shadowed built-ins
        :type pythonic_params: bool
        :param options: New style options dictionary.
        :type options: dict | None
        :param pass_context_arg_name: If not None URL request handling functions with an argument matching this name
            will be passed the framework's request context.
        :type pass_context_arg_name: str | None
        """
        self.debug = debug
        self.validator_map = validator_map
        self.resolver_error_handler = resolver_error_handler

        logger.debug('Loading specificatio()n: %s', specification,
                     extra={'swagger_yaml': specification,
                            'base_path': base_path,
                            'arguments': arguments,
                            'auth_all_paths': auth_all_paths})

        # Avoid validator having ability to modify specification
        self.specification = NewSpecification.load(specification, arguments=arguments)

        logger.debug('Read specification', extra={'spec': self.specification})

        self.options = options_module.ConnexionOptions(options, oas_version=self.specification.version)

        logger.debug('Options Loaded',
                     extra={'swagger_ui': self.options.openapi_console_ui_available,
                            'swagger_path': self.options.openapi_console_ui_from_dir,
                            'swagger_url': self.options.openapi_console_ui_path})

        self._set_base_path(base_path)

        logger.debug('Security Definitions: %s', self.specification.security_definitions)

        self.resolver = resolver or resolver_module.Resolver()

        logger.debug('Validate Responses: %s', str(validate_responses))
        self.validate_responses = validate_responses

        logger.debug('Strict Request Validation: %s', str(strict_validation))
        self.strict_validation = strict_validation

        logger.debug('Pythonic params: %s', str(pythonic_params))
        self.pythonic_params = pythonic_params

        logger.debug('pass_context_arg_name: %s', pass_context_arg_name)
        self.pass_context_arg_name = pass_context_arg_name

        self.security_handler_factory = self.make_security_handler_factory(pass_context_arg_name)

        if self.options.openapi_spec_available:
            self.add_openapi_json()
            self.add_openapi_yaml()

        if self.options.openapi_console_ui_available:
            self.add_swagger_ui()

        self.add_paths()

        if auth_all_paths:
            self.add_auth_on_not_found(
                self.specification.security,
                self.specification.security_definitions
            )

    def _set_blueprint(self):
        self.blueprint = ListBlueprint()
        for base_path in self.base_path:
            logger.debug('Creating API blueprint: %s', base_path)
            endpoint = flask_utils.flaskify_endpoint(base_path)
            self.blueprint[base_path] = flask.Blueprint(endpoint, __name__, url_prefix=base_path,
                                            template_folder=str(self.options.openapi_console_ui_from_dir))

    def add_openapi_json(self):
        return

    def add_openapi_yaml(self):
        return

    def add_swagger_ui(self):
        """
        Adds swagger ui to {base_path}/ui/
        """
        console_ui_path = self.options.openapi_console_ui_path.strip('/')
        logger.debug('Adding swagger-ui: %s/%s/',
                     self.base_path,
                     console_ui_path)

        if self.options.openapi_console_ui_config is not None:
            config_endpoint_name = f"{self.blueprint.name}_swagger_ui_config"
            config_file_url = '/{console_ui_path}/swagger-ui-config.json'.format(
                console_ui_path=console_ui_path)

            self.blueprint.add_url_rule(config_file_url,
                                        config_endpoint_name,
                                        lambda: flask.jsonify(self.options.openapi_console_ui_config))

        static_endpoint_name = f"{self.blueprint.name}_swagger_ui_static"
        static_files_url = '/{console_ui_path}/<path:filename>'.format(
            console_ui_path=console_ui_path)

        self.blueprint.add_url_rule(static_files_url,
                                    static_endpoint_name,
                                    self._handlers.console_ui_static_files)

        index_endpoint_name = f"{self.blueprint.name}_swagger_ui_index"
        console_ui_url = '/{console_ui_path}/'.format(
            console_ui_path=console_ui_path)

        self.blueprint.add_url_rule(console_ui_url,
                                    index_endpoint_name,
                                    self._handlers.console_ui_home)

class NewFlaskApp(flask_app.FlaskApp):

    def __init__(self, import_name, server='flask', extra_files=None, **kwargs):
        print("NewFlaskApp")
        abstract_app.AbstractApp.__init__(self, import_name, NewFlaskApi, server=server, **kwargs)
        self.extra_files = extra_files or []

    def add_api(self, specification, **kwargs):
        api = super().add_api(specification, **kwargs)
        for blueprint in api.blueprint:
            self.app.register_blueprint(blueprint)
        if isinstance(specification, (str, pathlib.Path)):
            self.extra_files.append(self.specification_dir / specification)
        return api

class NewSpecification(spec_module.Specification):

    @classmethod
    def from_dict(cls, spec):
        """
        Takes in a dictionary, and returns a Specification
        """
        def enforce_string_keys(obj):
            # YAML supports integer keys, but JSON does not
            if isinstance(obj, dict):
                return {
                    str(k): enforce_string_keys(v)
                    for k, v
                    in obj.items()
                }
            return obj

        spec = enforce_string_keys(spec)
        version = cls._get_spec_version(spec)
        if version < (3, 0, 0):
            return spec_module.Swagger2Specification(spec)
        return NewOpenAPISpecification(spec)

class NewOpenAPISpecification(spec_module.OpenAPISpecification):

    @property
    def base_path(self):
        servers = self._spec.get('servers', [])
        try:
            # assume we're the first server in list
            base_path = []
            for server in servers:
                server_vars = server.pop("variables", {})
                server['url'] = server['url'].format(
                    **{k: v['default'] for k, v
                        in server_vars.items()}
                )
                temp = urllib.parse.urlsplit(server['url']).path
                base_path.append(spec_module.canonical_base_path(temp))
        except IndexError:
            base_path = [spec_module.canonical_base_path('')]
        return base_path
