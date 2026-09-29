//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of openapi.api;

class AssetCreate {
  /// Returns a new [AssetCreate] instance.
  AssetCreate({
    this.attributes,
    this.avatarIconUid,
    this.inboundRelations = const [],
    this.isGlobal = false,
    this.key,
    required this.name,
    this.outboundRelations = const [],
    required this.schemaUid,
    this.type,
    required this.uid,
  });

  ///
  /// Please note: This property should have been non-nullable! Since the specification file
  /// does not include a default value (using the "default:" property), however, the generated
  /// source code must fall back to having a nullable type.
  /// Consider adding a "default:" property in the specification file to hide this note.
  ///
  Object? attributes;

  String? avatarIconUid;

  List<String> inboundRelations;

  bool isGlobal;

  String? key;

  String name;

  List<String> outboundRelations;

  String schemaUid;

  String? type;

  String uid;

  @override
  bool operator ==(Object other) => identical(this, other) || other is AssetCreate &&
    other.attributes == attributes &&
    other.avatarIconUid == avatarIconUid &&
    _deepEquality.equals(other.inboundRelations, inboundRelations) &&
    other.isGlobal == isGlobal &&
    other.key == key &&
    other.name == name &&
    _deepEquality.equals(other.outboundRelations, outboundRelations) &&
    other.schemaUid == schemaUid &&
    other.type == type &&
    other.uid == uid;

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (attributes == null ? 0 : attributes!.hashCode) +
    (avatarIconUid == null ? 0 : avatarIconUid!.hashCode) +
    (inboundRelations.hashCode) +
    (isGlobal.hashCode) +
    (key == null ? 0 : key!.hashCode) +
    (name.hashCode) +
    (outboundRelations.hashCode) +
    (schemaUid.hashCode) +
    (type == null ? 0 : type!.hashCode) +
    (uid.hashCode);

  @override
  String toString() => 'AssetCreate[attributes=$attributes, avatarIconUid=$avatarIconUid, inboundRelations=$inboundRelations, isGlobal=$isGlobal, key=$key, name=$name, outboundRelations=$outboundRelations, schemaUid=$schemaUid, type=$type, uid=$uid]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
    if (this.attributes != null) {
      json[r'attributes'] = this.attributes;
    } else {
      json[r'attributes'] = null;
    }
    if (this.avatarIconUid != null) {
      json[r'avatar_icon_uid'] = this.avatarIconUid;
    } else {
      json[r'avatar_icon_uid'] = null;
    }
      json[r'inbound_relations'] = this.inboundRelations;
      json[r'is_global'] = this.isGlobal;
    if (this.key != null) {
      json[r'key'] = this.key;
    } else {
      json[r'key'] = null;
    }
      json[r'name'] = this.name;
      json[r'outbound_relations'] = this.outboundRelations;
      json[r'schema_uid'] = this.schemaUid;
    if (this.type != null) {
      json[r'type'] = this.type;
    } else {
      json[r'type'] = null;
    }
      json[r'uid'] = this.uid;
    return json;
  }

  /// Returns a new [AssetCreate] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static AssetCreate? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        requiredKeys.forEach((key) {
          assert(json.containsKey(key), 'Required key "AssetCreate[$key]" is missing from JSON.');
          assert(json[key] != null, 'Required key "AssetCreate[$key]" has a null value in JSON.');
        });
        return true;
      }());

      return AssetCreate(
        attributes: mapValueOfType<Object>(json, r'attributes'),
        avatarIconUid: mapValueOfType<String>(json, r'avatar_icon_uid'),
        inboundRelations: json[r'inbound_relations'] is Iterable
            ? (json[r'inbound_relations'] as Iterable).cast<String>().toList(growable: false)
            : const [],
        isGlobal: mapValueOfType<bool>(json, r'is_global') ?? false,
        key: mapValueOfType<String>(json, r'key'),
        name: mapValueOfType<String>(json, r'name')!,
        outboundRelations: json[r'outbound_relations'] is Iterable
            ? (json[r'outbound_relations'] as Iterable).cast<String>().toList(growable: false)
            : const [],
        schemaUid: mapValueOfType<String>(json, r'schema_uid')!,
        type: mapValueOfType<String>(json, r'type'),
        uid: mapValueOfType<String>(json, r'uid')!,
      );
    }
    return null;
  }

  static List<AssetCreate> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <AssetCreate>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = AssetCreate.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, AssetCreate> mapFromJson(dynamic json) {
    final map = <String, AssetCreate>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = AssetCreate.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of AssetCreate-objects as value to a dart map
  static Map<String, List<AssetCreate>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<AssetCreate>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = AssetCreate.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'name',
    'schema_uid',
    'uid',
  };
}

