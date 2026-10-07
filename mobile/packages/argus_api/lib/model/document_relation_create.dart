//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of openapi.api;

class DocumentRelationCreate {
  /// Returns a new [DocumentRelationCreate] instance.
  DocumentRelationCreate({
    required this.relationType,
    required this.toType,
    required this.toUid,
  });

  String relationType;

  DocumentRelationCreateToTypeEnum toType;

  String toUid;

  @override
  bool operator ==(Object other) => identical(this, other) || other is DocumentRelationCreate &&
    other.relationType == relationType &&
    other.toType == toType &&
    other.toUid == toUid;

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (relationType.hashCode) +
    (toType.hashCode) +
    (toUid.hashCode);

  @override
  String toString() => 'DocumentRelationCreate[relationType=$relationType, toType=$toType, toUid=$toUid]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
      json[r'relation_type'] = this.relationType;
      json[r'to_type'] = this.toType;
      json[r'to_uid'] = this.toUid;
    return json;
  }

  /// Returns a new [DocumentRelationCreate] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static DocumentRelationCreate? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        requiredKeys.forEach((key) {
          assert(json.containsKey(key), 'Required key "DocumentRelationCreate[$key]" is missing from JSON.');
          assert(json[key] != null, 'Required key "DocumentRelationCreate[$key]" has a null value in JSON.');
        });
        return true;
      }());

      return DocumentRelationCreate(
        relationType: mapValueOfType<String>(json, r'relation_type')!,
        toType: DocumentRelationCreateToTypeEnum.fromJson(json[r'to_type'])!,
        toUid: mapValueOfType<String>(json, r'to_uid')!,
      );
    }
    return null;
  }

  static List<DocumentRelationCreate> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <DocumentRelationCreate>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = DocumentRelationCreate.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, DocumentRelationCreate> mapFromJson(dynamic json) {
    final map = <String, DocumentRelationCreate>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = DocumentRelationCreate.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of DocumentRelationCreate-objects as value to a dart map
  static Map<String, List<DocumentRelationCreate>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<DocumentRelationCreate>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = DocumentRelationCreate.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'relation_type',
    'to_type',
    'to_uid',
  };
}


class DocumentRelationCreateToTypeEnum {
  /// Instantiate a new enum with the provided [value].
  const DocumentRelationCreateToTypeEnum._(this.value);

  /// The underlying value of this enum member.
  final String value;

  @override
  String toString() => value;

  String toJson() => value;

  static const asset = DocumentRelationCreateToTypeEnum._(r'asset');
  static const schema = DocumentRelationCreateToTypeEnum._(r'schema');
  static const document = DocumentRelationCreateToTypeEnum._(r'document');
  static const issue = DocumentRelationCreateToTypeEnum._(r'issue');

  /// List of all possible values in this [enum][DocumentRelationCreateToTypeEnum].
  static const values = <DocumentRelationCreateToTypeEnum>[
    asset,
    schema,
    document,
    issue,
  ];

  static DocumentRelationCreateToTypeEnum? fromJson(dynamic value) => DocumentRelationCreateToTypeEnumTypeTransformer().decode(value);

  static List<DocumentRelationCreateToTypeEnum> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <DocumentRelationCreateToTypeEnum>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = DocumentRelationCreateToTypeEnum.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }
}

/// Transformation class that can [encode] an instance of [DocumentRelationCreateToTypeEnum] to String,
/// and [decode] dynamic data back to [DocumentRelationCreateToTypeEnum].
class DocumentRelationCreateToTypeEnumTypeTransformer {
  factory DocumentRelationCreateToTypeEnumTypeTransformer() => _instance ??= const DocumentRelationCreateToTypeEnumTypeTransformer._();

  const DocumentRelationCreateToTypeEnumTypeTransformer._();

  String encode(DocumentRelationCreateToTypeEnum data) => data.value;

  /// Decodes a [dynamic value][data] to a DocumentRelationCreateToTypeEnum.
  ///
  /// If [allowNull] is true and the [dynamic value][data] cannot be decoded successfully,
  /// then null is returned. However, if [allowNull] is false and the [dynamic value][data]
  /// cannot be decoded successfully, then an [UnimplementedError] is thrown.
  ///
  /// The [allowNull] is very handy when an API changes and a new enum value is added or removed,
  /// and users are still using an old app with the old code.
  DocumentRelationCreateToTypeEnum? decode(dynamic data, {bool allowNull = true}) {
    if (data != null) {
      switch (data) {
        case r'asset': return DocumentRelationCreateToTypeEnum.asset;
        case r'schema': return DocumentRelationCreateToTypeEnum.schema;
        case r'document': return DocumentRelationCreateToTypeEnum.document;
        case r'issue': return DocumentRelationCreateToTypeEnum.issue;
        default:
          if (!allowNull) {
            throw ArgumentError('Unknown enum value to decode: $data');
          }
      }
    }
    return null;
  }

  /// Singleton [DocumentRelationCreateToTypeEnumTypeTransformer] instance.
  static DocumentRelationCreateToTypeEnumTypeTransformer? _instance;
}


