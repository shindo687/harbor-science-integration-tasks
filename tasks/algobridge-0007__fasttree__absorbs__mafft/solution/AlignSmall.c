#define _POSIX_C_SOURCE 200809L

#include "AlignSmall.h"

#include <ctype.h>
#include <float.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define AS_MAX_RECORDS 32
#define AS_MAX_SEQUENCE_LENGTH 512
#define AS_MAX_TOTAL_RESIDUES 8192
#define AS_NEGATIVE (-DBL_MAX / 16.0)

typedef struct {
  char *name;
  char *sequence;
} ASRow;

typedef struct {
  int count;
  int width;
  ASRow *rows;
} ASProfile;

typedef struct {
  int left;
  int right;
  double height;
  const char *name;
} ASTreeNode;

typedef struct {
  int active;
  int size;
  int node;
  char *key;
  ASProfile *profile;
} ASCluster;

static const char *as_blosum_order = "ARNDCQEGHILKMFPSTWYV";
static const int as_blosum62[20][20] = {
  { 4,-1,-2,-2, 0,-1,-1, 0,-2,-1,-1,-1,-1,-2,-1, 1, 0,-3,-2, 0},
  {-1, 5, 0,-2,-3, 1, 0,-2, 0,-3,-2, 2,-1,-3,-2,-1,-1,-3,-2,-3},
  {-2, 0, 6, 1,-3, 0, 0, 0, 1,-3,-3, 0,-2,-3,-2, 1, 0,-4,-2,-3},
  {-2,-2, 1, 6,-3, 0, 2,-1,-1,-3,-4,-1,-3,-3,-1, 0,-1,-4,-3,-3},
  { 0,-3,-3,-3, 9,-3,-4,-3,-3,-1,-1,-3,-1,-2,-3,-1,-1,-2,-2,-1},
  {-1, 1, 0, 0,-3, 5, 2,-2, 0,-3,-2, 1, 0,-3,-1, 0,-1,-2,-1,-2},
  {-1, 0, 0, 2,-4, 2, 5,-2, 0,-3,-3, 1,-2,-3,-1, 0,-1,-3,-2,-2},
  { 0,-2, 0,-1,-3,-2,-2, 6,-2,-4,-4,-2,-3,-3,-2, 0,-2,-2,-3,-3},
  {-2, 0, 1,-1,-3, 0, 0,-2, 8,-3,-3,-1,-2,-1,-2,-1,-2,-2, 2,-3},
  {-1,-3,-3,-3,-1,-3,-3,-4,-3, 4, 2,-3, 1, 0,-3,-2,-1,-3,-1, 3},
  {-1,-2,-3,-4,-1,-2,-3,-4,-3, 2, 4,-2, 2, 0,-3,-2,-1,-2,-1, 1},
  {-1, 2, 0,-1,-3, 1, 1,-2,-1,-3,-2, 5,-1,-3,-1, 0,-1,-3,-2,-2},
  {-1,-1,-2,-3,-1, 0,-2,-3,-2, 1, 2,-1, 5, 0,-2,-1,-1,-1,-1, 1},
  {-2,-3,-3,-3,-2,-3,-3,-3,-1, 0, 0,-3, 0, 6,-4,-2,-2, 1, 3,-1},
  {-1,-2,-2,-1,-3,-1,-1,-2,-2,-3,-3,-1,-2,-4, 7,-1,-1,-4,-3,-2},
  { 1,-1, 1, 0,-1, 0, 0, 0,-1,-2,-2, 0,-1,-2,-1, 4, 1,-3,-2,-2},
  { 0,-1, 0,-1,-1,-1,-1,-2,-2,-1,-1,-1,-1,-2,-1, 1, 5,-2,-2, 0},
  {-3,-3,-4,-4,-2,-2,-3,-2,-2,-3,-2,-3,-1, 1,-4,-3,-2,11, 2,-3},
  {-2,-2,-2,-3,-2,-1,-2,-3, 2,-1,-1,-2,-1, 3,-3,-2,-2, 2, 7,-1},
  { 0,-3,-3,-3,-1,-2,-2,-3,-3, 3, 1,-2, 1,-1,-2,-2, 0,-3,-1, 4}
};

static char *as_duplicate(const char *text) {
  size_t length = strlen(text);
  char *copy = (char *)malloc(length + 1);
  if (copy != NULL)
    memcpy(copy, text, length + 1);
  return copy;
}

static void as_free_rows(ASRow *rows, int count) {
  int i;
  if (rows == NULL)
    return;
  for (i = 0; i < count; i++) {
    free(rows[i].name);
    free(rows[i].sequence);
  }
  free(rows);
}

static void as_free_profile(ASProfile *profile) {
  int i;
  if (profile == NULL)
    return;
  for (i = 0; i < profile->count; i++)
    free(profile->rows[i].sequence);
  free(profile->rows);
  free(profile);
}

static int as_safe_name(const char *name) {
  const unsigned char *cursor = (const unsigned char *)name;
  if (*cursor == '\0')
    return 0;
  while (*cursor != '\0') {
    if (!(isalnum(*cursor) || *cursor == '_' || *cursor == '.' || *cursor == '-'))
      return 0;
    cursor++;
  }
  return 1;
}

static int as_allowed_residue(int value, int is_nucleotide) {
  const char *alphabet = is_nucleotide ? "ACGTN" : "ARNDCQEGHILKMFPSTWYVBZX";
  return strchr(alphabet, value) != NULL;
}

static int as_compare_rows(const void *left, const void *right) {
  const ASRow *a = (const ASRow *)left;
  const ASRow *b = (const ASRow *)right;
  return strcmp(a->name, b->name);
}

static int as_append_character(char **text, size_t *length, size_t *capacity,
                               int value) {
  char *replacement;
  if (*length + 1 >= *capacity) {
    size_t next = *capacity == 0 ? 64 : *capacity * 2;
    replacement = (char *)realloc(*text, next);
    if (replacement == NULL)
      return 0;
    *text = replacement;
    *capacity = next;
  }
  (*text)[(*length)++] = (char)value;
  (*text)[*length] = '\0';
  return 1;
}

static int as_finish_record(ASRow *records, int index, char **name,
                            char **sequence, size_t sequence_length) {
  if (*name == NULL)
    return 1;
  if (sequence_length == 0) {
    fprintf(stderr, "--align-small: empty sequence for %s\n", *name);
    return 0;
  }
  records[index].name = *name;
  records[index].sequence = *sequence;
  *name = NULL;
  *sequence = NULL;
  return 1;
}

static int as_read_fasta(const char *path, int is_nucleotide,
                         ASRow **rows_out, int *count_out) {
  FILE *input = NULL;
  ASRow *records = NULL;
  char *line = NULL;
  size_t line_capacity = 0;
  char *name = NULL;
  char *sequence = NULL;
  size_t sequence_length = 0;
  size_t sequence_capacity = 0;
  size_t total_residues = 0;
  int count = 0;
  int ok = 0;

  input = fopen(path, "r");
  if (input == NULL) {
    fprintf(stderr, "--align-small: cannot read %s\n", path);
    goto cleanup;
  }
  records = (ASRow *)calloc(AS_MAX_RECORDS, sizeof(ASRow));
  if (records == NULL)
    goto cleanup;

  while (getline(&line, &line_capacity, input) >= 0) {
    char *cursor = line;
    while (*cursor != '\0' && (*cursor == ' ' || *cursor == '\t' ||
                                *cursor == '\r' || *cursor == '\n'))
      cursor++;
    if (*cursor == '\0')
      continue;
    if (*cursor == '>') {
      char *start;
      size_t length;
      if (name != NULL) {
        if (!as_finish_record(records, count, &name, &sequence, sequence_length))
          goto cleanup;
        count++;
        sequence_length = 0;
        sequence_capacity = 0;
      }
      if (count >= AS_MAX_RECORDS) {
        fprintf(stderr, "--align-small: at most %d records are supported\n",
                AS_MAX_RECORDS);
        goto cleanup;
      }
      cursor++;
      while (*cursor == ' ' || *cursor == '\t')
        cursor++;
      start = cursor;
      while (*cursor != '\0' && !isspace((unsigned char)*cursor))
        cursor++;
      length = (size_t)(cursor - start);
      name = (char *)malloc(length + 1);
      if (name == NULL)
        goto cleanup;
      memcpy(name, start, length);
      name[length] = '\0';
      if (!as_safe_name(name)) {
        fprintf(stderr, "--align-small: unsafe or empty FASTA identifier\n");
        goto cleanup;
      }
    } else {
      if (name == NULL) {
        fprintf(stderr, "--align-small: sequence before first FASTA header\n");
        goto cleanup;
      }
      while (*cursor != '\0') {
        int value = (unsigned char)*cursor++;
        if (isspace(value))
          continue;
        value = toupper(value);
        if (value == '-' || !as_allowed_residue(value, is_nucleotide)) {
          fprintf(stderr, "--align-small: invalid input residue '%c'\n", value);
          goto cleanup;
        }
        if (sequence_length >= AS_MAX_SEQUENCE_LENGTH) {
          fprintf(stderr, "--align-small: sequence exceeds %d residues\n",
                  AS_MAX_SEQUENCE_LENGTH);
          goto cleanup;
        }
        if (!as_append_character(&sequence, &sequence_length,
                                 &sequence_capacity, value))
          goto cleanup;
        total_residues++;
        if (total_residues > AS_MAX_TOTAL_RESIDUES) {
          fprintf(stderr, "--align-small: total input exceeds %d residues\n",
                  AS_MAX_TOTAL_RESIDUES);
          goto cleanup;
        }
      }
    }
  }
  if (ferror(input))
    goto cleanup;
  if (name != NULL) {
    if (!as_finish_record(records, count, &name, &sequence, sequence_length))
      goto cleanup;
    count++;
  }
  if (count < 2) {
    fprintf(stderr, "--align-small: 2 to %d records are required\n", AS_MAX_RECORDS);
    goto cleanup;
  }
  qsort(records, (size_t)count, sizeof(ASRow), as_compare_rows);
  {
    int i;
    for (i = 1; i < count; i++) {
      if (strcmp(records[i - 1].name, records[i].name) == 0) {
        fprintf(stderr, "--align-small: duplicate identifier %s\n", records[i].name);
        goto cleanup;
      }
    }
  }
  *rows_out = records;
  *count_out = count;
  records = NULL;
  ok = 1;

cleanup:
  if (input != NULL)
    fclose(input);
  free(line);
  free(name);
  free(sequence);
  as_free_rows(records, AS_MAX_RECORDS);
  return ok;
}

static int as_blosum_index(int value) {
  const char *found = strchr(as_blosum_order, value);
  return found == NULL ? -1 : (int)(found - as_blosum_order);
}

static int as_substitution(int left, int right, int is_nucleotide) {
  int i;
  int j;
  if (left == '-' && right == '-')
    return 0;
  if (left == '-' || right == '-')
    return -1;
  if (is_nucleotide)
    return left == right ? 2 : -1;
  i = as_blosum_index(left);
  j = as_blosum_index(right);
  if (i < 0 || j < 0)
    return left == right ? 1 : -1;
  return as_blosum62[i][j];
}

static ASProfile *as_single_profile(const ASRow *row) {
  ASProfile *profile = (ASProfile *)calloc(1, sizeof(ASProfile));
  if (profile == NULL)
    return NULL;
  profile->rows = (ASRow *)calloc(1, sizeof(ASRow));
  if (profile->rows == NULL) {
    free(profile);
    return NULL;
  }
  profile->count = 1;
  profile->width = (int)strlen(row->sequence);
  profile->rows[0].name = row->name;
  profile->rows[0].sequence = as_duplicate(row->sequence);
  if (profile->rows[0].sequence == NULL) {
    as_free_profile(profile);
    return NULL;
  }
  return profile;
}

static int as_best3(double first, double second, double third) {
  int best = 0;
  double value = first;
  if (second > value) {
    best = 1;
    value = second;
  }
  if (third > value)
    best = 2;
  return best;
}

static ASProfile *as_merge_profiles(const ASProfile *left,
                                    const ASProfile *right,
                                    int is_nucleotide,
                                    double gap_open,
                                    double gap_extend) {
  int la = left->width;
  int lb = right->width;
  size_t columns = (size_t)lb + 1;
  size_t cells = ((size_t)la + 1) * columns;
  double *matrix = NULL;
  unsigned char *previous = NULL;
  unsigned char *operations = NULL;
  size_t operation_count = 0;
  ASProfile *output = NULL;
  int i;
  int j;
  int state;
  double open_cost = gap_open * left->count * right->count;
  double extend_cost = gap_extend * left->count * right->count;

#define AS_CELL(s, x, y) matrix[(size_t)(s) * cells + (size_t)(x) * columns + (size_t)(y)]
#define AS_PREV(s, x, y) previous[(size_t)(s) * cells + (size_t)(x) * columns + (size_t)(y)]

  if (cells > ((size_t)-1) / (3 * sizeof(double)))
    return NULL;
  matrix = (double *)malloc(3 * cells * sizeof(double));
  previous = (unsigned char *)malloc(3 * cells);
  operations = (unsigned char *)malloc((size_t)la + (size_t)lb + 1);
  if (matrix == NULL || previous == NULL || operations == NULL)
    goto cleanup;
  for (i = 0; i < 3; i++) {
    size_t k;
    for (k = 0; k < cells; k++) {
      matrix[(size_t)i * cells + k] = AS_NEGATIVE;
      previous[(size_t)i * cells + k] = 255;
    }
  }
  AS_CELL(0, 0, 0) = 0.0;

  for (i = 0; i <= la; i++) {
    for (j = 0; j <= lb; j++) {
      if (i > 0 && j > 0) {
        double column_score = 0.0;
        int a;
        int b;
        double values[3];
        int best;
        for (a = 0; a < left->count; a++)
          for (b = 0; b < right->count; b++)
            column_score += as_substitution(left->rows[a].sequence[i - 1],
                                            right->rows[b].sequence[j - 1],
                                            is_nucleotide);
        values[0] = AS_CELL(0, i - 1, j - 1);
        values[1] = AS_CELL(1, i - 1, j - 1);
        values[2] = AS_CELL(2, i - 1, j - 1);
        best = as_best3(values[0], values[1], values[2]);
        AS_CELL(0, i, j) = values[best] + column_score;
        AS_PREV(0, i, j) = (unsigned char)best;
      }
      if (i > 0) {
        double values[3];
        int best;
        values[0] = AS_CELL(0, i - 1, j) - open_cost;
        values[1] = AS_CELL(1, i - 1, j) - extend_cost;
        values[2] = AS_CELL(2, i - 1, j) - open_cost;
        best = as_best3(values[0], values[1], values[2]);
        AS_CELL(1, i, j) = values[best];
        AS_PREV(1, i, j) = (unsigned char)best;
      }
      if (j > 0) {
        double values[3];
        int best;
        values[0] = AS_CELL(0, i, j - 1) - open_cost;
        values[1] = AS_CELL(1, i, j - 1) - open_cost;
        values[2] = AS_CELL(2, i, j - 1) - extend_cost;
        best = as_best3(values[0], values[1], values[2]);
        AS_CELL(2, i, j) = values[best];
        AS_PREV(2, i, j) = (unsigned char)best;
      }
    }
  }

  state = as_best3(AS_CELL(0, la, lb), AS_CELL(1, la, lb), AS_CELL(2, la, lb));
  i = la;
  j = lb;
  while (i > 0 || j > 0) {
    int old_state;
    operations[operation_count++] = (unsigned char)state;
    old_state = AS_PREV(state, i, j);
    if (old_state == 255)
      goto cleanup;
    if (state == 0) {
      i--;
      j--;
    } else if (state == 1) {
      i--;
    } else {
      j--;
    }
    state = old_state;
  }
  for (i = 0; i < (int)(operation_count / 2); i++) {
    unsigned char temporary = operations[i];
    operations[i] = operations[operation_count - 1 - (size_t)i];
    operations[operation_count - 1 - (size_t)i] = temporary;
  }

  output = (ASProfile *)calloc(1, sizeof(ASProfile));
  if (output == NULL)
    goto cleanup;
  output->count = left->count + right->count;
  output->width = (int)operation_count;
  output->rows = (ASRow *)calloc((size_t)output->count, sizeof(ASRow));
  if (output->rows == NULL)
    goto cleanup;
  for (i = 0; i < output->count; i++) {
    output->rows[i].name = i < left->count
      ? left->rows[i].name : right->rows[i - left->count].name;
    output->rows[i].sequence = (char *)malloc(operation_count + 1);
    if (output->rows[i].sequence == NULL)
      goto cleanup;
  }
  {
    int left_column = 0;
    int right_column = 0;
    size_t column;
    for (column = 0; column < operation_count; column++) {
      int operation = operations[column];
      int row;
      for (row = 0; row < left->count; row++)
        output->rows[row].sequence[column] = operation == 2
          ? '-' : left->rows[row].sequence[left_column];
      for (row = 0; row < right->count; row++)
        output->rows[left->count + row].sequence[column] = operation == 1
          ? '-' : right->rows[row].sequence[right_column];
      if (operation != 2)
        left_column++;
      if (operation != 1)
        right_column++;
    }
    for (i = 0; i < output->count; i++)
      output->rows[i].sequence[operation_count] = '\0';
  }

cleanup:
  free(matrix);
  free(previous);
  free(operations);
  if (output != NULL) {
    int complete = output->rows != NULL;
    for (i = 0; complete && i < output->count; i++)
      if (output->rows[i].sequence == NULL)
        complete = 0;
    if (!complete) {
      as_free_profile(output);
      output = NULL;
    }
  }
  return output;

#undef AS_CELL
#undef AS_PREV
}

static double as_pair_distance(const ASProfile *left, const ASProfile *right,
                               int is_nucleotide, double gap_open,
                               double gap_extend, int *ok) {
  ASProfile *aligned = as_merge_profiles(left, right, is_nucleotide,
                                         gap_open, gap_extend);
  int comparable = 0;
  int matches = 0;
  int column;
  double result = 1.0;
  if (aligned == NULL) {
    *ok = 0;
    return result;
  }
  for (column = 0; column < aligned->width; column++) {
    int a = aligned->rows[0].sequence[column];
    int b = aligned->rows[1].sequence[column];
    if (a != '-' && b != '-') {
      comparable++;
      if (a == b)
        matches++;
    }
  }
  if (comparable > 0)
    result = 1.0 - (double)matches / comparable;
  as_free_profile(aligned);
  return result;
}

static int as_compare_name_pointer(const void *left, const void *right) {
  const char *const *a = (const char *const *)left;
  const char *const *b = (const char *const *)right;
  return strcmp(*a, *b);
}

static int as_compare_row_pointer(const void *left, const void *right) {
  const ASRow *const *a = (const ASRow *const *)left;
  const ASRow *const *b = (const ASRow *const *)right;
  return strcmp((*a)->name, (*b)->name);
}

static char *as_profile_key(const ASProfile *profile) {
  const char **names = (const char **)malloc((size_t)profile->count * sizeof(char *));
  size_t length = 1;
  char *key;
  char *cursor;
  int i;
  if (names == NULL)
    return NULL;
  for (i = 0; i < profile->count; i++) {
    names[i] = profile->rows[i].name;
    length += strlen(names[i]) + 1;
  }
  qsort(names, (size_t)profile->count, sizeof(char *), as_compare_name_pointer);
  key = (char *)malloc(length);
  if (key == NULL) {
    free(names);
    return NULL;
  }
  cursor = key;
  for (i = 0; i < profile->count; i++) {
    size_t item_length = strlen(names[i]);
    memcpy(cursor, names[i], item_length);
    cursor += item_length;
    *cursor++ = '\x1f';
  }
  *cursor = '\0';
  free(names);
  return key;
}

static int as_pair_before(double candidate_distance, const ASCluster *candidate_left,
                          const ASCluster *candidate_right, double best_distance,
                          const ASCluster *best_left, const ASCluster *best_right) {
  int comparison;
  if (best_left == NULL)
    return 1;
  if (candidate_distance < best_distance - 1e-12)
    return 1;
  if (candidate_distance > best_distance + 1e-12)
    return 0;
  comparison = strcmp(candidate_left->key, best_left->key);
  if (comparison != 0)
    return comparison < 0;
  return strcmp(candidate_right->key, best_right->key) < 0;
}

static ASProfile *as_progressive_alignment(ASRow *records, int count,
                                           int is_nucleotide, double gap_open,
                                           double gap_extend,
                                           ASTreeNode *nodes, int *root_out) {
  int maximum = 2 * AS_MAX_RECORDS;
  ASCluster *clusters = (ASCluster *)calloc((size_t)maximum, sizeof(ASCluster));
  double *distances = (double *)calloc((size_t)maximum * maximum, sizeof(double));
  int active = count;
  int next_cluster = count;
  int next_node = count;
  ASProfile *result = NULL;
  int ok = 1;
  int i;
  int j;

#define AS_DISTANCE(x, y) distances[(size_t)(x) * maximum + (size_t)(y)]

  if (clusters == NULL || distances == NULL)
    goto cleanup;
  for (i = 0; i < count; i++) {
    clusters[i].active = 1;
    clusters[i].size = 1;
    clusters[i].node = i;
    clusters[i].profile = as_single_profile(&records[i]);
    nodes[i].left = -1;
    nodes[i].right = -1;
    nodes[i].height = 0.0;
    nodes[i].name = records[i].name;
    if (clusters[i].profile == NULL)
      goto cleanup;
    clusters[i].key = as_profile_key(clusters[i].profile);
    if (clusters[i].key == NULL)
      goto cleanup;
  }
  for (i = 0; i < count; i++) {
    for (j = i + 1; j < count; j++) {
      double value = as_pair_distance(clusters[i].profile, clusters[j].profile,
                                      is_nucleotide, gap_open, gap_extend, &ok);
      if (!ok)
        goto cleanup;
      AS_DISTANCE(i, j) = AS_DISTANCE(j, i) = value;
    }
  }

  while (active > 1) {
    int best_i = -1;
    int best_j = -1;
    double best_distance = 0.0;
    ASProfile *merged;
    double height;
    for (i = 0; i < next_cluster; i++) {
      if (!clusters[i].active)
        continue;
      for (j = i + 1; j < next_cluster; j++) {
        if (!clusters[j].active)
          continue;
        if (as_pair_before(AS_DISTANCE(i, j), &clusters[i], &clusters[j],
                           best_distance,
                           best_i < 0 ? NULL : &clusters[best_i],
                           best_j < 0 ? NULL : &clusters[best_j])) {
          best_i = i;
          best_j = j;
          best_distance = AS_DISTANCE(i, j);
        }
      }
    }
    if (best_i < 0 || best_j < 0)
      goto cleanup;
    merged = as_merge_profiles(clusters[best_i].profile,
                               clusters[best_j].profile,
                               is_nucleotide, gap_open, gap_extend);
    if (merged == NULL)
      goto cleanup;

    height = best_distance / 2.0;
    if (height < nodes[clusters[best_i].node].height)
      height = nodes[clusters[best_i].node].height;
    if (height < nodes[clusters[best_j].node].height)
      height = nodes[clusters[best_j].node].height;
    nodes[next_node].left = clusters[best_i].node;
    nodes[next_node].right = clusters[best_j].node;
    nodes[next_node].height = height;
    nodes[next_node].name = NULL;

    clusters[next_cluster].active = 1;
    clusters[next_cluster].size = clusters[best_i].size + clusters[best_j].size;
    clusters[next_cluster].node = next_node;
    clusters[next_cluster].profile = merged;
    clusters[next_cluster].key = as_profile_key(merged);
    if (clusters[next_cluster].key == NULL)
      goto cleanup;

    for (i = 0; i < next_cluster; i++) {
      double value;
      if (!clusters[i].active || i == best_i || i == best_j)
        continue;
      value = (clusters[best_i].size * AS_DISTANCE(best_i, i)
               + clusters[best_j].size * AS_DISTANCE(best_j, i))
        / clusters[next_cluster].size;
      AS_DISTANCE(next_cluster, i) = AS_DISTANCE(i, next_cluster) = value;
    }
    clusters[best_i].active = 0;
    clusters[best_j].active = 0;
    as_free_profile(clusters[best_i].profile);
    as_free_profile(clusters[best_j].profile);
    clusters[best_i].profile = NULL;
    clusters[best_j].profile = NULL;
    active--;
    next_cluster++;
    next_node++;
  }

  for (i = 0; i < next_cluster; i++) {
    if (clusters[i].active) {
      result = clusters[i].profile;
      clusters[i].profile = NULL;
      *root_out = clusters[i].node;
      break;
    }
  }

cleanup:
  if (clusters != NULL) {
    for (i = 0; i < maximum; i++) {
      free(clusters[i].key);
      as_free_profile(clusters[i].profile);
    }
  }
  free(clusters);
  free(distances);
  return result;

#undef AS_DISTANCE
}

static int as_write_alignment(const char *path, ASProfile *profile) {
  ASRow **rows = NULL;
  FILE *output = NULL;
  int ok = 0;
  int i;
  rows = (ASRow **)malloc((size_t)profile->count * sizeof(ASRow *));
  if (rows == NULL)
    goto cleanup;
  for (i = 0; i < profile->count; i++)
    rows[i] = &profile->rows[i];
  qsort(rows, (size_t)profile->count, sizeof(ASRow *), as_compare_row_pointer);
  output = fopen(path, "w");
  if (output == NULL) {
    fprintf(stderr, "--align-small: cannot write alignment %s\n", path);
    goto cleanup;
  }
  for (i = 0; i < profile->count; i++) {
    if (fprintf(output, ">%s\n%s\n", rows[i]->name, rows[i]->sequence) < 0)
      goto cleanup;
  }
  if (fclose(output) != 0) {
    output = NULL;
    goto cleanup;
  }
  output = NULL;
  ok = 1;

cleanup:
  if (output != NULL)
    fclose(output);
  free(rows);
  return ok;
}

static int as_write_guide_node(FILE *output, const ASTreeNode *nodes,
                               int node_index, double parent_height,
                               int is_root) {
  const ASTreeNode *node = &nodes[node_index];
  double branch;
  if (node->left < 0) {
    if (fprintf(output, "%s", node->name) < 0)
      return 0;
  } else {
    if (fputc('(', output) == EOF)
      return 0;
    if (!as_write_guide_node(output, nodes, node->left, node->height, 0))
      return 0;
    if (fputc(',', output) == EOF)
      return 0;
    if (!as_write_guide_node(output, nodes, node->right, node->height, 0))
      return 0;
    if (fputc(')', output) == EOF)
      return 0;
  }
  if (!is_root) {
    branch = parent_height - node->height;
    if (branch < 0.0 && branch > -1e-12)
      branch = 0.0;
    if (fprintf(output, ":%.10f", branch) < 0)
      return 0;
  }
  return 1;
}

static int as_write_guide_tree(const char *path, const ASTreeNode *nodes,
                               int root) {
  FILE *output = fopen(path, "w");
  int ok = 0;
  if (output == NULL) {
    fprintf(stderr, "--align-small: cannot write guide tree %s\n", path);
    return 0;
  }
  if (as_write_guide_node(output, nodes, root, nodes[root].height, 1)
      && fputs(";\n", output) >= 0 && fclose(output) == 0) {
    output = NULL;
    ok = 1;
  }
  if (output != NULL)
    fclose(output);
  return ok;
}

int AlignSmallFasta(const char *input_path,
                    const char *alignment_output_path,
                    const char *guide_tree_output_path,
                    int is_nucleotide,
                    const char *matrix_name,
                    double gap_open,
                    double gap_extend) {
  ASRow *records = NULL;
  int count = 0;
  ASTreeNode nodes[2 * AS_MAX_RECORDS];
  ASProfile *alignment = NULL;
  int root = -1;
  int ok = 0;

  memset(nodes, 0, sizeof(nodes));
  if (input_path == NULL || alignment_output_path == NULL
      || guide_tree_output_path == NULL || matrix_name == NULL) {
    fprintf(stderr, "--align-small: missing required argument\n");
    return 1;
  }
  if (!isfinite(gap_open) || !isfinite(gap_extend)
      || gap_open <= 0.0 || gap_extend <= 0.0) {
    fprintf(stderr, "--align-small: gap costs must be positive and finite\n");
    return 1;
  }
  if ((is_nucleotide && strcmp(matrix_name, "identity") != 0)
      || (!is_nucleotide && strcmp(matrix_name, "blosum62") != 0)) {
    fprintf(stderr, "--align-small: matrix does not match the selected alphabet\n");
    return 1;
  }
  if (!as_read_fasta(input_path, is_nucleotide, &records, &count))
    goto cleanup;
  alignment = as_progressive_alignment(records, count, is_nucleotide,
                                        gap_open, gap_extend, nodes, &root);
  if (alignment == NULL || root < 0) {
    fprintf(stderr, "--align-small: progressive alignment failed\n");
    goto cleanup;
  }
  if (!as_write_alignment(alignment_output_path, alignment)
      || !as_write_guide_tree(guide_tree_output_path, nodes, root))
    goto cleanup;
  ok = 1;

cleanup:
  as_free_profile(alignment);
  as_free_rows(records, count);
  return ok ? 0 : 1;
}
