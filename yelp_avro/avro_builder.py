# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals

import collections
import copy

from avro import schema


class AvroSchemaBuilder(object):
    """
    AvroSchemaBuilder creates json-formatted Avro schemas. It has `create_*`
    function for each primitive type to create primitive types. To create a
    complex type, start with corresponding `begin_*` function and finish it
    with `end` function.

    It defers the schema validation until the end of schema building. When
    the schema building ends, it constructs the corresponding schema object
    which will validate the the syntax of the Avro json object.

    Usage:
      ab = AvroSchemaBuilder()

      - building a record schema:
        record = ab.begin_record(
            'user',
            namespace='yelp'
        ).add_field(
            'id',
            typ=ab.create_int()
        ).add_field(
            'fav_color',
            typ=ab.begin_enum('color_enum', ['red', 'blue']).end()
        ).end()

      - building an enum schema:
        enum_schema = ab.begin_enum('color_enum', ['red', 'blue']).end()

      - building an array schema:
        array_schema = ab.begin_array(ab.create_string()).end()
    """

    def __init__(self):
        self._schema_json = None  # current avro schema in build
        self._schema_tracker = []

    @classmethod
    def create_null(cls):
        return 'null'

    @classmethod
    def create_boolean(cls):
        return 'boolean'

    @classmethod
    def create_int(cls):
        return 'int'

    @classmethod
    def create_long(cls):
        return 'long'

    @classmethod
    def create_float(cls):
        return 'float'

    @classmethod
    def create_double(cls):
        return 'double'

    @classmethod
    def create_bytes(cls):
        return 'bytes'

    @classmethod
    def create_string(cls):
        return 'string'

    def begin_enum(self, name, symbols, namespace=None, aliases=None,
                   doc=None, **metadata):
        enum_schema = {
            'type': 'enum',
            'name': name,
            'symbols': symbols
        }
        if namespace:
            self._set_namespace(enum_schema, namespace)
        if aliases:
            self._set_aliases(enum_schema, aliases)
        if doc:
            self._set_doc(enum_schema, doc)
        enum_schema.update(metadata)

        self._save_current_schema()
        self._set_current_schema(enum_schema)
        return self

    def begin_fixed(self, name, size, namespace=None, aliases=None,
                    **metadata):
        fixed_schema = {
            'type': 'fixed',
            'name': name,
            'size': size
        }
        if namespace:
            self._set_namespace(fixed_schema, namespace)
        if aliases:
            self._set_aliases(fixed_schema, aliases)
        fixed_schema.update(metadata)

        self._save_current_schema()
        self._set_current_schema(fixed_schema)
        return self

    def begin_decimal_fixed(self, precision, scale, size, name,
                            namespace=None, **metadata):
        fixed_decimal_schema = {
            'type': 'fixed',
            'logicalType': 'decimal',
            'name': name,
            'precision': precision,
            'scale': scale,
            'size': size
        }
        if namespace:
            self._set_namespace(fixed_decimal_schema, namespace)
        fixed_decimal_schema.update(metadata)

        self._save_current_schema()
        self._set_current_schema(fixed_decimal_schema)
        return self

    def begin_decimal_bytes(self, precision, scale, **metadata):
        bytes_decimal_schema = {
            'type': 'bytes',
            'logicalType': 'decimal',
            'precision': precision,
            'scale': scale
        }

        bytes_decimal_schema.update(metadata)
        self._save_current_schema()
        self._set_current_schema(bytes_decimal_schema)
        return self

    def begin_array(self, items_schema, **metadata):
        array_schema = {'type': 'array', 'items': items_schema}
        array_schema.update(metadata)
        self._save_current_schema()
        self._set_current_schema(array_schema)
        return self

    def begin_map(self, values_schema, **metadata):
        map_schema = {'type': 'map', 'values': values_schema}
        map_schema.update(metadata)
        self._save_current_schema()
        self._set_current_schema(map_schema)
        return self

    def begin_record(self, name, namespace=None, aliases=None, doc=None,
                     **metadata):
        record_schema = {'type': 'record', 'name': name, 'fields': []}
        if namespace is not None:
            self._set_namespace(record_schema, namespace)
        if aliases:
            self._set_aliases(record_schema, aliases)
        if doc:
            self._set_doc(record_schema, doc)
        record_schema.update(metadata)

        self._save_current_schema()
        self._set_current_schema(record_schema)
        return self

    def add_field(self, name, typ, has_default=False, default_value=None,
                  sort_order=None, aliases=None, doc=None, **metadata):
        field = self.create_field(
            name,
            typ,
            has_default=has_default,
            default_value=default_value,
            sort_order=sort_order,
            aliases=aliases,
            doc=doc,
            **metadata
        )
        self._schema_json['fields'].append(field)
        return self

    @classmethod
    def create_field(cls, name, typ, has_default=False, default_value=None,
                     sort_order=None, aliases=None, doc=None, **metadata):
        return AvroField.from_attributes(
            name,
            typ,
            has_default=has_default,
            default_value=default_value,
            sort_order=sort_order,
            aliases=aliases,
            doc=doc,
            **metadata
        ).field_json

    def begin_union(self, *avro_schemas):
        union_schema = list(avro_schemas)
        self._save_current_schema()
        self._set_current_schema(union_schema)
        return self

    def end(self):
        if not self._schema_tracker:
            # this is the top level schema; do the schema validation
            schema_obj = schema.make_avsc_object(self._schema_json)
            self._schema_json = None
            return schema_obj.to_json()

        current_schema_json = self._schema_json
        self._restore_current_schema()
        return current_schema_json

    def _save_current_schema(self):
        if self._schema_json:
            self._schema_tracker.append(self._schema_json)

    def _set_current_schema(self, avro_schema):
        self._schema_json = avro_schema

    def _restore_current_schema(self):
        self._schema_json = self._schema_tracker.pop()

    @classmethod
    def _set_namespace(cls, avro_schema, namespace):
        avro_schema['namespace'] = namespace

    @classmethod
    def _set_aliases(cls, avro_schema, aliases):
        avro_schema['aliases'] = aliases

    @classmethod
    def _set_doc(cls, avro_schema, doc):
        avro_schema['doc'] = doc

    def begin_nullable_type(self, schema_type, default_value=None):
        """Create an Avro schema that represents the nullable `schema_type`.
        The nullable type is a union schema type with `null` primitive type.
        The given default value is used to determine whether the `null` type
        should be the first item in the union type.
        """
        null_type = self.create_null()

        src_type = copy.deepcopy(schema_type)
        if self.is_nullable_type(schema_type):
            nullable_schema = src_type
        else:
            typ = src_type if isinstance(src_type, list) else [src_type]
            if default_value is None:
                typ.insert(0, null_type)
            else:
                typ.append(null_type)
            nullable_schema = self.begin_union(*typ).end()

        self._save_current_schema()
        self._set_current_schema(nullable_schema)
        return self

    @classmethod
    def is_nullable_type(cls, schema_type):
        """Whether the given type is a nullable type, either it is `null` or
        a union Avro schema type which contains `null`.
        """
        null_type = cls.create_null()
        return (
            schema_type is not None and (
                schema_type == null_type or
                (isinstance(schema_type, collections.Iterable) and
                    any(typ == null_type for typ in schema_type))
            )
        )

    def begin_with_schema_json(self, schema_json):
        """Begin building the given schema json object.  Similar to other
        `begin_*` functions, it doesn't validate the input schema json until
        the end of schema.
        """
        self._save_current_schema()
        self._set_current_schema(copy.deepcopy(schema_json))
        return self

    def remove_field(self, field_name):
        """Remove the specified field from the fields in the current schema.
        It throws `ValueError` exception if given field cannot be found.
        """
        index, field = self._get_field_and_index(field_name)
        del self._schema_json['fields'][index]
        return self

    def insert_field(self, field, index):
        """Insert the given field at specified field list index.

        Args:
            field (dict): Python json representation of an Avro field.
            index (int): position index of the field to be inserted.
        """
        self._schema_json['fields'].insert(index, field)
        return self

    def insert_fields(self, fields, index):
        """Insert the given field list at specified field list index.

        Args:
            fields(List[dict]): List of Python json representation of Avro
                fields.
            index (int): start position index to insert the given fields.
        """
        record_fields = self._schema_json['fields']
        self._schema_json['fields'] = (record_fields[:index] +
                                       fields +
                                       record_fields[index:])
        return self

    def get_field_index(self, field_name):
        """Get the field list index of given field name.  It throws
        `ValueError` exception if given field cannot be found.

        Args:
            field_name (str): name of the field in interest
        """
        index, _ = self._get_field_and_index(field_name)
        return index

    def get_field(self, field_name):
        """Get the field json dict of given field name.  It throws
        `ValueError` exception if given field cannot be found.

        Args:
            field_name (str): name of the field in interest
        """
        _, field = self._get_field_and_index(field_name)
        return field

    def _get_field_and_index(self, field_name):
        fields = self._get_fields()
        for i, field in enumerate(fields):
            if field['name'] == field_name:
                return i, field
        raise ValueError("Cannot find field named {0}".format(field_name))

    def _get_fields(self):
        return self._schema_json.get('fields', [])

    def replace_field(self, old_field_name, new_fields, preserve_null=True):
        """ Replace an existing field with 0 or more new fields, preserving
        the 'nullability' on the type if required.

        Args:
            old_field_name (str): The name of the field to replace.
            new_fields (list(dict)): A list of dictionaries containing kwargs
                for `add_field`. At the minimum it is expected that the keys
                "name" and "typ" will be provided. If this list is empty the
                effect will be the same as calling `remove_field`
            preserve_null (boolean): If true then if `old_field_name` had
                a "null" in it's type list, the new fields will as well.
        """
        # TODO(joshszep|DATAPIPE-472): Revisit the logic for this
        field = self.get_field(old_field_name)
        null_type = self.create_null()
        add_null = preserve_null and null_type in field['type']
        self.remove_field(old_field_name)
        for field_kwargs in new_fields:
            new_field_type = field_kwargs['typ']
            _kwargs = copy.deepcopy(field_kwargs)
            if add_null and null_type not in new_field_type:
                if isinstance(field_kwargs['typ'], list):
                    _kwargs['typ'].insert(0, null_type)
                else:
                    _kwargs['typ'] = [null_type, new_field_type]
            self.add_field(**_kwargs)

    def clear(self):
        """Clear the schemas that are built so far."""
        self._schema_json = None
        self._schema_tracker = []


class AvroField(object):
    """This class is used to hold an Avro field schema and provide an easy way
    to manipulate the field without directly dealing with Python json dict.
    """

    _reserved_keys = {'name', 'type', 'default', 'order', 'aliases', 'doc'}

    def __init__(self, field_json):
        self._field_json = field_json

    @classmethod
    def from_attributes(cls, name, typ, has_default=False, default_value=None,
                        sort_order=None, aliases=None, doc=None, **metadata):
        avro_field = AvroField({'name': name})
        avro_field.field_type = typ
        if has_default:
            avro_field.default_value = default_value
        if sort_order:
            avro_field.sort_order = sort_order
        if aliases:
            avro_field.aliases = aliases
        if doc:
            avro_field.doc = doc
        avro_field.set_metadata(**metadata)
        return avro_field

    @property
    def field_json(self):
        return self._field_json

    @property
    def name(self):
        return self._field_json['name']

    @property
    def field_type(self):
        return self._field_json['type']

    @field_type.setter
    def field_type(self, new_type):
        self._field_json['type'] = new_type

    @property
    def has_default(self):
        return 'default' in self._field_json

    @property
    def default_value(self):
        return self._field_json['default']

    @default_value.setter
    def default_value(self, new_default_value):
        self._field_json['default'] = new_default_value

    @property
    def sort_order(self):
        return self._field_json.get('order')

    @sort_order.setter
    def sort_order(self, new_sort_order):
        self._field_json['order'] = new_sort_order

    @property
    def aliases(self):
        return self._field_json.get('aliases')

    @aliases.setter
    def aliases(self, new_aliases):
        self._field_json['aliases'] = new_aliases

    @property
    def doc(self):
        return self._field_json.get('doc')

    @doc.setter
    def doc(self, new_doc):
        self._field_json['doc'] = new_doc

    @property
    def metadata(self):
        return {
            k: v for k, v in self._field_json.items()
            if k not in self._reserved_keys
        }

    def clear_metadata(self):
        self._field_json = {
            k: v for k, v in self._field_json.items()
            if k in self._reserved_keys
        }

    def set_metadata(self, **metadata):
        self._field_json.update(metadata)
