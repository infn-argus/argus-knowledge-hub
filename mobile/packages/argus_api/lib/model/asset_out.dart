//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of openapi.api;

class AssetOut {
  /// Returns a new [AssetOut] instance.
  AssetOut({
    required this.attributes,
    this.avatarIconUid,
    required this.createdAt,
    this.deletedAt,
    this.inboundRelations = const [],
    required this.isGlobal,
    required this.key,
    required this.name,
    this.outboundRelations = const [],
    this.recordStatus = 'Active',
    required this.schemaUid,
    required this.type,
    required this.uid,
    required this.updatedAt,
    this.version,
    required this.workspaceId,
  });

  Object attributes;

  String? avatarIconUid;

  DateTime createdAt;

  DateTime? deletedAt;

  List<String> inboundRelations;

  bool isGlobal;

  String key;

  String name;

  List<String> outboundRelations;

  String recordStatus;

  String schemaUid;

  String type;

  String uid;

  DateTime updatedAt;

  int? version;

  String workspaceId;

  @override
  bool operator ==(Object other) => identical(this, other) || other is AssetOut &&
    other.attributes == attributes &&
    other.avatarIconUid == avatarIconUid &&
    other.createdAt == createdAt &&
    other.deletedAt == deletedAt &&
    _deepEquality.equals(other.inboundRelations, inboundRelations) &&
    other.isGlobal == isGlobal &&
    other.key == key &&
    other.name == name &&
    _deepEquality.equals(other.outboundRelations, outboundRelations) &&
    other.recordStatus == recordStatus &&
    other.schemaUid == schemaUid &&
    other.type == type &&
    other.uid == uid &&
    other.updatedAt == updatedAt &&
    other.version == version &&
    other.workspaceId == workspaceId;

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (attributes.hashCode) +
    (avatarIconUid == null ? 0 : avatarIconUid!.hashCode) +
    (createdAt.hashCode) +
    (deletedAt == null ? 0 : deletedAt!.hashCode) +
    (inboundRelations.hashCode) +
    (isGlobal.hashCode) +
    (key.hashCode) +
    (name.hashCode) +
    (outboundRelations.hashCode) +
    (recordStatus.hashCode) +
    (schemaUid.hashCode) +
    (type.hashCode) +
    (uid.hashCode) +
    (updatedAt.hashCode) +
    (version == null ? 0 : version!.hashCode) +
    (workspaceId.hashCode);

  @override
  String toString() => 'AssetOut[attributes=$attributes, avatarIconUid=$avatarIconUid, createdAt=$createdAt, deletedAt=$deletedAt, inboundRelations=$inboundRelations, isGlobal=$isGlobal, key=$key, name=$name, outboundRelations=$outboundRelations, recordStatus=$recordStatus, schemaUid=$schemaUid, type=$type, uid=$uid, updatedAt=$updatedAt, version=$version, workspaceId=$workspaceId]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
      json[r'attributes'] = this.attributes;
    if (this.avatarIconUid != null) {
      json[r'avatar_icon_uid'] = this.avatarIconUid;
    } else {
      json[r'avatar_icon_uid'] = null;
    }
      json[r'created_at'] = this.createdAt.toUtc().toIso8601String();
    if (this.deletedAt != null) {
      json[r'deleted_at'] = this.deletedAt!.toUtc().toIso8601String();
    } else {
      json[r'deleted_at'] = null;
    }
      json[r'inbound_relations'] = this.inboundRelations;
      json[r'is_global'] = this.isGlobal;
      json[r'key'] = this.key;
      json[r'name'] = this.name;
      json[r'outbound_relations'] = this.outboundRelations;
      json[r'record_status'] = this.recordStatus;
      json[r'schema_uid'] = this.schemaUid;
      json[r'type'] = this.type;
      json[r'uid'] = this.uid;
      json[r'updated_at'] = this.updatedAt.toUtc().toIso8601String();
    if (this.version != null) {
      json[r'version'] = this.version;
    } else {
      json[r'version'] = null;
    }
      json[r'workspace_id'] = this.workspaceId;
    return json;
  }

  /// Returns a new [AssetOut] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static AssetOut? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        requiredKeys.forEach((key) {
          assert(json.containsKey(key), 'Required key "AssetOut[$key]" is missing from JSON.');
          assert(json[key] != null, 'Required key "AssetOut[$key]" has a null value in JSON.');
        });
        return true;
      }());

      return AssetOut(
        attributes: mapValueOfType<Object>(json, r'attributes')!,
        avatarIconUid: mapValueOfType<String>(json, r'avatar_icon_uid'),
        createdAt: mapDateTime(json, r'created_at', r'')!,
        deletedAt: mapDateTime(json, r'deleted_at', r''),
        inboundRelations: json[r'inbound_relations'] is Iterable
            ? (json[r'inbound_relations'] as Iterable).cast<String>().toList(growable: false)
            : const [],
        isGlobal: mapValueOfType<bool>(json, r'is_global')!,
        key: mapValueOfType<String>(json, r'key')!,
        name: mapValueOfType<String>(json, r'name')!,
        outboundRelations: json[r'outbound_relations'] is Iterable
            ? (json[r'outbound_relations'] as Iterable).cast<String>().toList(growable: false)
            : const [],
        recordStatus: mapValueOfType<String>(json, r'record_status') ?? 'Active',
        schemaUid: mapValueOfType<String>(json, r'schema_uid')!,
        type: mapValueOfType<String>(json, r'type')!,
        uid: mapValueOfType<String>(json, r'uid')!,
        updatedAt: mapDateTime(json, r'updated_at', r'')!,
        version: mapValueOfType<int>(json, r'version'),
        workspaceId: mapValueOfType<String>(json, r'workspace_id')!,
      );
    }
    return null;
  }

  static List<AssetOut> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <AssetOut>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = AssetOut.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, AssetOut> mapFromJson(dynamic json) {
    final map = <String, AssetOut>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = AssetOut.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of AssetOut-objects as value to a dart map
  static Map<String, List<AssetOut>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<AssetOut>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = AssetOut.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'attributes',
    'created_at',
    'inbound_relations',
    'is_global',
    'key',
    'name',
    'outbound_relations',
    'schema_uid',
    'type',
    'uid',
    'updated_at',
    'workspace_id',
  };
}

