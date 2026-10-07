//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of openapi.api;

class GlobalValueOut {
  /// Returns a new [GlobalValueOut] instance.
  GlobalValueOut({
    this.allowedEguList = const [],
    this.appliesTo = 'objects',
    this.constraints,
    required this.createdAt,
    this.defaultValue,
    this.egu,
    this.enabled = true,
    this.indexed = false,
    this.isSystemDefault = false,
    required this.key,
    this.maxCardinality,
    this.minCardinality,
    this.multiValue = false,
    required this.name,
    this.options,
    this.readOnly = false,
    this.referenceType,
    this.required_ = false,
    required this.type,
    required this.uid,
    this.unique = false,
    required this.updatedAt,
    this.visible = true,
    required this.workspaceId,
  });

  List<String>? allowedEguList;

  String appliesTo;

  Object? constraints;

  DateTime createdAt;

  String? defaultValue;

  String? egu;

  bool enabled;

  bool indexed;

  bool isSystemDefault;

  String key;

  int? maxCardinality;

  int? minCardinality;

  bool multiValue;

  String name;

  Object? options;

  bool readOnly;

  String? referenceType;

  bool required_;

  String type;

  String uid;

  bool unique;

  DateTime updatedAt;

  bool visible;

  String workspaceId;

  @override
  bool operator ==(Object other) => identical(this, other) || other is GlobalValueOut &&
    _deepEquality.equals(other.allowedEguList, allowedEguList) &&
    other.appliesTo == appliesTo &&
    other.constraints == constraints &&
    other.createdAt == createdAt &&
    other.defaultValue == defaultValue &&
    other.egu == egu &&
    other.enabled == enabled &&
    other.indexed == indexed &&
    other.isSystemDefault == isSystemDefault &&
    other.key == key &&
    other.maxCardinality == maxCardinality &&
    other.minCardinality == minCardinality &&
    other.multiValue == multiValue &&
    other.name == name &&
    other.options == options &&
    other.readOnly == readOnly &&
    other.referenceType == referenceType &&
    other.required_ == required_ &&
    other.type == type &&
    other.uid == uid &&
    other.unique == unique &&
    other.updatedAt == updatedAt &&
    other.visible == visible &&
    other.workspaceId == workspaceId;

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (allowedEguList == null ? 0 : allowedEguList!.hashCode) +
    (appliesTo.hashCode) +
    (constraints == null ? 0 : constraints!.hashCode) +
    (createdAt.hashCode) +
    (defaultValue == null ? 0 : defaultValue!.hashCode) +
    (egu == null ? 0 : egu!.hashCode) +
    (enabled.hashCode) +
    (indexed.hashCode) +
    (isSystemDefault.hashCode) +
    (key.hashCode) +
    (maxCardinality == null ? 0 : maxCardinality!.hashCode) +
    (minCardinality == null ? 0 : minCardinality!.hashCode) +
    (multiValue.hashCode) +
    (name.hashCode) +
    (options == null ? 0 : options!.hashCode) +
    (readOnly.hashCode) +
    (referenceType == null ? 0 : referenceType!.hashCode) +
    (required_.hashCode) +
    (type.hashCode) +
    (uid.hashCode) +
    (unique.hashCode) +
    (updatedAt.hashCode) +
    (visible.hashCode) +
    (workspaceId.hashCode);

  @override
  String toString() => 'GlobalValueOut[allowedEguList=$allowedEguList, appliesTo=$appliesTo, constraints=$constraints, createdAt=$createdAt, defaultValue=$defaultValue, egu=$egu, enabled=$enabled, indexed=$indexed, isSystemDefault=$isSystemDefault, key=$key, maxCardinality=$maxCardinality, minCardinality=$minCardinality, multiValue=$multiValue, name=$name, options=$options, readOnly=$readOnly, referenceType=$referenceType, required_=$required_, type=$type, uid=$uid, unique=$unique, updatedAt=$updatedAt, visible=$visible, workspaceId=$workspaceId]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
    if (this.allowedEguList != null) {
      json[r'allowed_egu_list'] = this.allowedEguList;
    } else {
      json[r'allowed_egu_list'] = null;
    }
      json[r'applies_to'] = this.appliesTo;
    if (this.constraints != null) {
      json[r'constraints'] = this.constraints;
    } else {
      json[r'constraints'] = null;
    }
      json[r'created_at'] = this.createdAt.toUtc().toIso8601String();
    if (this.defaultValue != null) {
      json[r'default_value'] = this.defaultValue;
    } else {
      json[r'default_value'] = null;
    }
    if (this.egu != null) {
      json[r'egu'] = this.egu;
    } else {
      json[r'egu'] = null;
    }
      json[r'enabled'] = this.enabled;
      json[r'indexed'] = this.indexed;
      json[r'is_system_default'] = this.isSystemDefault;
      json[r'key'] = this.key;
    if (this.maxCardinality != null) {
      json[r'max_cardinality'] = this.maxCardinality;
    } else {
      json[r'max_cardinality'] = null;
    }
    if (this.minCardinality != null) {
      json[r'min_cardinality'] = this.minCardinality;
    } else {
      json[r'min_cardinality'] = null;
    }
      json[r'multi_value'] = this.multiValue;
      json[r'name'] = this.name;
    if (this.options != null) {
      json[r'options'] = this.options;
    } else {
      json[r'options'] = null;
    }
      json[r'read_only'] = this.readOnly;
    if (this.referenceType != null) {
      json[r'reference_type'] = this.referenceType;
    } else {
      json[r'reference_type'] = null;
    }
      json[r'required'] = this.required_;
      json[r'type'] = this.type;
      json[r'uid'] = this.uid;
      json[r'unique'] = this.unique;
      json[r'updated_at'] = this.updatedAt.toUtc().toIso8601String();
      json[r'visible'] = this.visible;
      json[r'workspace_id'] = this.workspaceId;
    return json;
  }

  /// Returns a new [GlobalValueOut] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static GlobalValueOut? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        requiredKeys.forEach((key) {
          assert(json.containsKey(key), 'Required key "GlobalValueOut[$key]" is missing from JSON.');
          assert(json[key] != null, 'Required key "GlobalValueOut[$key]" has a null value in JSON.');
        });
        return true;
      }());

      return GlobalValueOut(
        allowedEguList: json[r'allowed_egu_list'] is Iterable
            ? (json[r'allowed_egu_list'] as Iterable).cast<String>().toList(growable: false)
            : const [],
        appliesTo: mapValueOfType<String>(json, r'applies_to') ?? 'objects',
        constraints: mapValueOfType<Object>(json, r'constraints'),
        createdAt: mapDateTime(json, r'created_at', r'')!,
        defaultValue: mapValueOfType<String>(json, r'default_value'),
        egu: mapValueOfType<String>(json, r'egu'),
        enabled: mapValueOfType<bool>(json, r'enabled') ?? true,
        indexed: mapValueOfType<bool>(json, r'indexed') ?? false,
        isSystemDefault: mapValueOfType<bool>(json, r'is_system_default') ?? false,
        key: mapValueOfType<String>(json, r'key')!,
        maxCardinality: mapValueOfType<int>(json, r'max_cardinality'),
        minCardinality: mapValueOfType<int>(json, r'min_cardinality'),
        multiValue: mapValueOfType<bool>(json, r'multi_value') ?? false,
        name: mapValueOfType<String>(json, r'name')!,
        options: mapValueOfType<Object>(json, r'options'),
        readOnly: mapValueOfType<bool>(json, r'read_only') ?? false,
        referenceType: mapValueOfType<String>(json, r'reference_type'),
        required_: mapValueOfType<bool>(json, r'required') ?? false,
        type: mapValueOfType<String>(json, r'type')!,
        uid: mapValueOfType<String>(json, r'uid')!,
        unique: mapValueOfType<bool>(json, r'unique') ?? false,
        updatedAt: mapDateTime(json, r'updated_at', r'')!,
        visible: mapValueOfType<bool>(json, r'visible') ?? true,
        workspaceId: mapValueOfType<String>(json, r'workspace_id')!,
      );
    }
    return null;
  }

  static List<GlobalValueOut> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <GlobalValueOut>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = GlobalValueOut.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, GlobalValueOut> mapFromJson(dynamic json) {
    final map = <String, GlobalValueOut>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = GlobalValueOut.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of GlobalValueOut-objects as value to a dart map
  static Map<String, List<GlobalValueOut>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<GlobalValueOut>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = GlobalValueOut.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'created_at',
    'key',
    'name',
    'type',
    'uid',
    'updated_at',
    'workspace_id',
  };
}

