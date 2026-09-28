//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of openapi.api;

class IssueOut {
  /// Returns a new [IssueOut] instance.
  IssueOut({
    this.assetUid,
    this.assignee,
    required this.attributes,
    this.closedAt,
    required this.createdAt,
    this.createdBy,
    this.deletedAt,
    this.description,
    this.dueDate,
    this.labels = const [],
    this.priority,
    this.schemaUid,
    required this.state,
    required this.title,
    required this.uid,
    required this.updatedAt,
    required this.version,
    required this.workspaceId,
  });

  String? assetUid;

  String? assignee;

  Object attributes;

  DateTime? closedAt;

  DateTime createdAt;

  String? createdBy;

  DateTime? deletedAt;

  String? description;

  DateTime? dueDate;

  List<String> labels;

  String? priority;

  String? schemaUid;

  String state;

  String title;

  String uid;

  DateTime updatedAt;

  int version;

  String workspaceId;

  @override
  bool operator ==(Object other) => identical(this, other) || other is IssueOut &&
    other.assetUid == assetUid &&
    other.assignee == assignee &&
    other.attributes == attributes &&
    other.closedAt == closedAt &&
    other.createdAt == createdAt &&
    other.createdBy == createdBy &&
    other.deletedAt == deletedAt &&
    other.description == description &&
    other.dueDate == dueDate &&
    _deepEquality.equals(other.labels, labels) &&
    other.priority == priority &&
    other.schemaUid == schemaUid &&
    other.state == state &&
    other.title == title &&
    other.uid == uid &&
    other.updatedAt == updatedAt &&
    other.version == version &&
    other.workspaceId == workspaceId;

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (assetUid == null ? 0 : assetUid!.hashCode) +
    (assignee == null ? 0 : assignee!.hashCode) +
    (attributes.hashCode) +
    (closedAt == null ? 0 : closedAt!.hashCode) +
    (createdAt.hashCode) +
    (createdBy == null ? 0 : createdBy!.hashCode) +
    (deletedAt == null ? 0 : deletedAt!.hashCode) +
    (description == null ? 0 : description!.hashCode) +
    (dueDate == null ? 0 : dueDate!.hashCode) +
    (labels.hashCode) +
    (priority == null ? 0 : priority!.hashCode) +
    (schemaUid == null ? 0 : schemaUid!.hashCode) +
    (state.hashCode) +
    (title.hashCode) +
    (uid.hashCode) +
    (updatedAt.hashCode) +
    (version.hashCode) +
    (workspaceId.hashCode);

  @override
  String toString() => 'IssueOut[assetUid=$assetUid, assignee=$assignee, attributes=$attributes, closedAt=$closedAt, createdAt=$createdAt, createdBy=$createdBy, deletedAt=$deletedAt, description=$description, dueDate=$dueDate, labels=$labels, priority=$priority, schemaUid=$schemaUid, state=$state, title=$title, uid=$uid, updatedAt=$updatedAt, version=$version, workspaceId=$workspaceId]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
    if (this.assetUid != null) {
      json[r'asset_uid'] = this.assetUid;
    } else {
      json[r'asset_uid'] = null;
    }
    if (this.assignee != null) {
      json[r'assignee'] = this.assignee;
    } else {
      json[r'assignee'] = null;
    }
      json[r'attributes'] = this.attributes;
    if (this.closedAt != null) {
      json[r'closed_at'] = this.closedAt!.toUtc().toIso8601String();
    } else {
      json[r'closed_at'] = null;
    }
      json[r'created_at'] = this.createdAt.toUtc().toIso8601String();
    if (this.createdBy != null) {
      json[r'created_by'] = this.createdBy;
    } else {
      json[r'created_by'] = null;
    }
    if (this.deletedAt != null) {
      json[r'deleted_at'] = this.deletedAt!.toUtc().toIso8601String();
    } else {
      json[r'deleted_at'] = null;
    }
    if (this.description != null) {
      json[r'description'] = this.description;
    } else {
      json[r'description'] = null;
    }
    if (this.dueDate != null) {
      json[r'due_date'] = this.dueDate!.toUtc().toIso8601String();
    } else {
      json[r'due_date'] = null;
    }
      json[r'labels'] = this.labels;
    if (this.priority != null) {
      json[r'priority'] = this.priority;
    } else {
      json[r'priority'] = null;
    }
    if (this.schemaUid != null) {
      json[r'schema_uid'] = this.schemaUid;
    } else {
      json[r'schema_uid'] = null;
    }
      json[r'state'] = this.state;
      json[r'title'] = this.title;
      json[r'uid'] = this.uid;
      json[r'updated_at'] = this.updatedAt.toUtc().toIso8601String();
      json[r'version'] = this.version;
      json[r'workspace_id'] = this.workspaceId;
    return json;
  }

  /// Returns a new [IssueOut] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static IssueOut? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        requiredKeys.forEach((key) {
          assert(json.containsKey(key), 'Required key "IssueOut[$key]" is missing from JSON.');
          assert(json[key] != null, 'Required key "IssueOut[$key]" has a null value in JSON.');
        });
        return true;
      }());

      return IssueOut(
        assetUid: mapValueOfType<String>(json, r'asset_uid'),
        assignee: mapValueOfType<String>(json, r'assignee'),
        attributes: mapValueOfType<Object>(json, r'attributes')!,
        closedAt: mapDateTime(json, r'closed_at', r''),
        createdAt: mapDateTime(json, r'created_at', r'')!,
        createdBy: mapValueOfType<String>(json, r'created_by'),
        deletedAt: mapDateTime(json, r'deleted_at', r''),
        description: mapValueOfType<String>(json, r'description'),
        dueDate: mapDateTime(json, r'due_date', r''),
        labels: json[r'labels'] is Iterable
            ? (json[r'labels'] as Iterable).cast<String>().toList(growable: false)
            : const [],
        priority: mapValueOfType<String>(json, r'priority'),
        schemaUid: mapValueOfType<String>(json, r'schema_uid'),
        state: mapValueOfType<String>(json, r'state')!,
        title: mapValueOfType<String>(json, r'title')!,
        uid: mapValueOfType<String>(json, r'uid')!,
        updatedAt: mapDateTime(json, r'updated_at', r'')!,
        version: mapValueOfType<int>(json, r'version')!,
        workspaceId: mapValueOfType<String>(json, r'workspace_id')!,
      );
    }
    return null;
  }

  static List<IssueOut> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <IssueOut>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = IssueOut.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, IssueOut> mapFromJson(dynamic json) {
    final map = <String, IssueOut>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = IssueOut.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of IssueOut-objects as value to a dart map
  static Map<String, List<IssueOut>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<IssueOut>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = IssueOut.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'attributes',
    'created_at',
    'labels',
    'state',
    'title',
    'uid',
    'updated_at',
    'version',
    'workspace_id',
  };
}

