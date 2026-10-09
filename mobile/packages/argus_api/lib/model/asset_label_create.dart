//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of openapi.api;

class AssetLabelCreate {
  /// Returns a new [AssetLabelCreate] instance.
  AssetLabelCreate({
    this.confidence,
    required this.createdAt,
    required this.issuer,
    this.metadataJson,
    this.namespace,
    required this.type,
    required this.uid,
    required this.updatedAt,
    required this.value,
    this.verified = false,
  });

  num? confidence;

  DateTime createdAt;

  String issuer;

  Object? metadataJson;

  String? namespace;

  String type;

  String uid;

  DateTime updatedAt;

  String value;

  bool verified;

  @override
  bool operator ==(Object other) => identical(this, other) || other is AssetLabelCreate &&
    other.confidence == confidence &&
    other.createdAt == createdAt &&
    other.issuer == issuer &&
    other.metadataJson == metadataJson &&
    other.namespace == namespace &&
    other.type == type &&
    other.uid == uid &&
    other.updatedAt == updatedAt &&
    other.value == value &&
    other.verified == verified;

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (confidence == null ? 0 : confidence!.hashCode) +
    (createdAt.hashCode) +
    (issuer.hashCode) +
    (metadataJson == null ? 0 : metadataJson!.hashCode) +
    (namespace == null ? 0 : namespace!.hashCode) +
    (type.hashCode) +
    (uid.hashCode) +
    (updatedAt.hashCode) +
    (value.hashCode) +
    (verified.hashCode);

  @override
  String toString() => 'AssetLabelCreate[confidence=$confidence, createdAt=$createdAt, issuer=$issuer, metadataJson=$metadataJson, namespace=$namespace, type=$type, uid=$uid, updatedAt=$updatedAt, value=$value, verified=$verified]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
    if (this.confidence != null) {
      json[r'confidence'] = this.confidence;
    } else {
      json[r'confidence'] = null;
    }
      json[r'created_at'] = this.createdAt.toUtc().toIso8601String();
      json[r'issuer'] = this.issuer;
    if (this.metadataJson != null) {
      json[r'metadata_json'] = this.metadataJson;
    } else {
      json[r'metadata_json'] = null;
    }
    if (this.namespace != null) {
      json[r'namespace'] = this.namespace;
    } else {
      json[r'namespace'] = null;
    }
      json[r'type'] = this.type;
      json[r'uid'] = this.uid;
      json[r'updated_at'] = this.updatedAt.toUtc().toIso8601String();
      json[r'value'] = this.value;
      json[r'verified'] = this.verified;
    return json;
  }

  /// Returns a new [AssetLabelCreate] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static AssetLabelCreate? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        requiredKeys.forEach((key) {
          assert(json.containsKey(key), 'Required key "AssetLabelCreate[$key]" is missing from JSON.');
          assert(json[key] != null, 'Required key "AssetLabelCreate[$key]" has a null value in JSON.');
        });
        return true;
      }());

      return AssetLabelCreate(
        confidence: json[r'confidence'] == null
            ? null
            : num.parse('${json[r'confidence']}'),
        createdAt: mapDateTime(json, r'created_at', r'')!,
        issuer: mapValueOfType<String>(json, r'issuer')!,
        metadataJson: mapValueOfType<Object>(json, r'metadata_json'),
        namespace: mapValueOfType<String>(json, r'namespace'),
        type: mapValueOfType<String>(json, r'type')!,
        uid: mapValueOfType<String>(json, r'uid')!,
        updatedAt: mapDateTime(json, r'updated_at', r'')!,
        value: mapValueOfType<String>(json, r'value')!,
        verified: mapValueOfType<bool>(json, r'verified') ?? false,
      );
    }
    return null;
  }

  static List<AssetLabelCreate> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <AssetLabelCreate>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = AssetLabelCreate.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, AssetLabelCreate> mapFromJson(dynamic json) {
    final map = <String, AssetLabelCreate>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = AssetLabelCreate.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of AssetLabelCreate-objects as value to a dart map
  static Map<String, List<AssetLabelCreate>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<AssetLabelCreate>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = AssetLabelCreate.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'created_at',
    'issuer',
    'type',
    'uid',
    'updated_at',
    'value',
  };
}

