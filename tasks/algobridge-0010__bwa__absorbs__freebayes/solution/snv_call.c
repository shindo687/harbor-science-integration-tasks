#include <ctype.h>
#include <errno.h>
#include <getopt.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "snv_call.h"

#define SKIP_FLAGS (0x4 | 0x100 | 0x200 | 0x400 | 0x800)

typedef struct {
    unsigned char base;
    unsigned char base_quality;
    unsigned char mapping_quality;
    unsigned char forward;
    unsigned short bases_left;
    unsigned short bases_right;
} observation_t;

typedef struct {
    observation_t *items;
    size_t count;
    size_t capacity;
} site_t;

typedef struct {
    char *name;
    char *sequence;
    size_t length;
    size_t sequence_capacity;
    site_t *sites;
} contig_t;

typedef struct {
    contig_t *items;
    size_t count;
    size_t capacity;
} reference_t;

typedef struct {
    const char *reference_path;
    const char *sample;
    const char *sam_path;
    int ploidy;
    int min_base_quality;
    int min_mapping_quality;
    int min_alternate_count;
    long double min_alternate_fraction;
    long double theta;
} options_t;

typedef struct {
    int count;
    int forward;
    int placed_left;
    int placed_start;
} balance_t;

static void *checked_realloc(void *pointer, size_t size)
{
    void *result = realloc(pointer, size);
    if (result == NULL) {
        fprintf(stderr, "snv-call: out of memory\n");
        exit(2);
    }
    return result;
}

static char *checked_strdup(const char *text)
{
    size_t length = strlen(text) + 1;
    char *copy = checked_realloc(NULL, length);
    memcpy(copy, text, length);
    return copy;
}

static void append_sequence(contig_t *contig, const char *text)
{
    size_t offset;
    size_t additional = 0;
    for (offset = 0; text[offset] != '\0'; ++offset) {
        if (!isspace((unsigned char)text[offset])) {
            ++additional;
        }
    }
    if (contig->length + additional + 1 > contig->sequence_capacity) {
        size_t capacity = contig->sequence_capacity == 0 ? 1024 : contig->sequence_capacity;
        while (capacity < contig->length + additional + 1) {
            capacity *= 2;
        }
        contig->sequence = checked_realloc(contig->sequence, capacity);
        contig->sequence_capacity = capacity;
    }
    for (offset = 0; text[offset] != '\0'; ++offset) {
        if (!isspace((unsigned char)text[offset])) {
            contig->sequence[contig->length++] = (char)toupper((unsigned char)text[offset]);
        }
    }
    contig->sequence[contig->length] = '\0';
}

static contig_t *append_contig(reference_t *reference, const char *name)
{
    contig_t *contig;
    if (reference->count == reference->capacity) {
        reference->capacity = reference->capacity == 0 ? 4 : reference->capacity * 2;
        reference->items = checked_realloc(reference->items,
            reference->capacity * sizeof(*reference->items));
    }
    contig = &reference->items[reference->count++];
    memset(contig, 0, sizeof(*contig));
    contig->name = checked_strdup(name);
    return contig;
}

static reference_t load_reference(const char *path)
{
    reference_t reference = {0};
    contig_t *current = NULL;
    FILE *handle = fopen(path, "r");
    char *line = NULL;
    size_t capacity = 0;
    ssize_t length;
    if (handle == NULL) {
        fprintf(stderr, "snv-call: cannot open reference %s: %s\n", path, strerror(errno));
        exit(2);
    }
    while ((length = getline(&line, &capacity, handle)) >= 0) {
        if (length > 0 && line[0] == '>') {
            char *end = line + 1;
            while (*end != '\0' && !isspace((unsigned char)*end)) {
                ++end;
            }
            *end = '\0';
            if (line[1] == '\0') {
                fprintf(stderr, "snv-call: empty FASTA contig name\n");
                exit(2);
            }
            current = append_contig(&reference, line + 1);
        } else if (current != NULL) {
            append_sequence(current, line);
        }
    }
    free(line);
    fclose(handle);
    if (reference.count == 0) {
        fprintf(stderr, "snv-call: reference contains no contigs\n");
        exit(2);
    }
    for (size_t index = 0; index < reference.count; ++index) {
        reference.items[index].sites = calloc(reference.items[index].length,
            sizeof(*reference.items[index].sites));
        if (reference.items[index].sites == NULL && reference.items[index].length != 0) {
            fprintf(stderr, "snv-call: out of memory\n");
            exit(2);
        }
    }
    return reference;
}

static contig_t *find_contig(reference_t *reference, const char *name)
{
    size_t index;
    for (index = 0; index < reference->count; ++index) {
        if (strcmp(reference->items[index].name, name) == 0) {
            return &reference->items[index];
        }
    }
    return NULL;
}

static void add_observation(site_t *site, observation_t observation)
{
    if (site->count == site->capacity) {
        site->capacity = site->capacity == 0 ? 8 : site->capacity * 2;
        site->items = checked_realloc(site->items, site->capacity * sizeof(*site->items));
    }
    site->items[site->count++] = observation;
}

static int base_index(char base)
{
    switch (toupper((unsigned char)base)) {
    case 'A': return 0;
    case 'C': return 1;
    case 'G': return 2;
    case 'T': return 3;
    default: return -1;
    }
}

static void consume_alignment(reference_t *reference, char **fields, int field_count,
    const options_t *options)
{
    contig_t *contig;
    const char *cigar;
    const char *sequence;
    const char *qualities;
    unsigned long value = 0;
    size_t reference_offset;
    size_t query_offset = 0;
    size_t read_length;
    int flag;
    int mapping_quality;
    size_t cigar_offset;

    if (field_count < 11) {
        return;
    }
    flag = atoi(fields[1]);
    if ((flag & SKIP_FLAGS) != 0) {
        return;
    }
    mapping_quality = atoi(fields[4]);
    if (mapping_quality < options->min_mapping_quality || mapping_quality < 0) {
        return;
    }
    contig = find_contig(reference, fields[2]);
    if (contig == NULL || strcmp(fields[5], "*") == 0) {
        return;
    }
    reference_offset = (size_t)strtoull(fields[3], NULL, 10);
    if (reference_offset == 0) {
        return;
    }
    --reference_offset;
    cigar = fields[5];
    sequence = fields[9];
    qualities = fields[10];
    read_length = strlen(sequence);
    if (strcmp(qualities, "*") == 0 || strlen(qualities) != read_length) {
        return;
    }

    for (cigar_offset = 0; cigar[cigar_offset] != '\0'; ++cigar_offset) {
        char operation = cigar[cigar_offset];
        if (isdigit((unsigned char)operation)) {
            value = value * 10 + (unsigned long)(operation - '0');
            continue;
        }
        if (value == 0) {
            return;
        }
        if (operation == 'M' || operation == '=' || operation == 'X') {
            unsigned long offset;
            for (offset = 0; offset < value; ++offset) {
                size_t ref_pos = reference_offset + offset;
                size_t query_pos = query_offset + offset;
                int quality;
                observation_t observation;
                if (ref_pos >= contig->length || query_pos >= read_length) {
                    continue;
                }
                quality = (unsigned char)qualities[query_pos] - 33;
                if (quality < options->min_base_quality || base_index(sequence[query_pos]) < 0) {
                    continue;
                }
                observation.base = (unsigned char)toupper((unsigned char)sequence[query_pos]);
                observation.base_quality = (unsigned char)(quality > 255 ? 255 : quality);
                observation.mapping_quality = (unsigned char)(mapping_quality > 255 ? 255 : mapping_quality);
                observation.forward = (flag & 0x10) == 0;
                observation.bases_left = (unsigned short)(query_pos > 65535 ? 65535 : query_pos);
                observation.bases_right = (unsigned short)(read_length - query_pos - 1 > 65535
                    ? 65535 : read_length - query_pos - 1);
                add_observation(&contig->sites[ref_pos], observation);
            }
            reference_offset += value;
            query_offset += value;
        } else if (operation == 'I' || operation == 'S') {
            query_offset += value;
        } else if (operation == 'D' || operation == 'N') {
            reference_offset += value;
        } else if (operation != 'H' && operation != 'P') {
            return;
        }
        value = 0;
    }
}

static void load_sam(reference_t *reference, const options_t *options)
{
    FILE *handle = strcmp(options->sam_path, "-") == 0 ? stdin : fopen(options->sam_path, "r");
    char *line = NULL;
    size_t capacity = 0;
    ssize_t length;
    if (handle == NULL) {
        fprintf(stderr, "snv-call: cannot open SAM %s: %s\n", options->sam_path, strerror(errno));
        exit(2);
    }
    while ((length = getline(&line, &capacity, handle)) >= 0) {
        char *fields[64];
        int field_count = 0;
        char *cursor;
        if (length == 0 || line[0] == '@') {
            continue;
        }
        cursor = line;
        while (field_count < (int)(sizeof(fields) / sizeof(fields[0]))) {
            char *tab;
            fields[field_count++] = cursor;
            tab = strchr(cursor, '\t');
            if (tab == NULL) {
                char *newline = strchr(cursor, '\n');
                if (newline != NULL) {
                    *newline = '\0';
                }
                break;
            }
            *tab = '\0';
            cursor = tab + 1;
        }
        consume_alignment(reference, fields, field_count, options);
    }
    free(line);
    if (handle != stdin) {
        fclose(handle);
    }
}

static long double factorial_ln(int value)
{
    static const long double cofactors[] = {
        76.18009173L, -86.50532033L, 24.01409822L,
        -1.231739516L, 0.120858003e-2L, -0.536382e-5L,
    };
    long double x1;
    long double tmp;
    long double series = 1.0L;
    int index;
    if (value <= 0) {
        return value == 0 ? 0.0L : -1.0L;
    }
    x1 = (long double)value;
    tmp = x1 + 5.5L;
    tmp -= (x1 + 0.5L) * logl(tmp);
    for (index = 0; index < 6; ++index) {
        x1 += 1.0L;
        series += cofactors[index] / x1;
    }
    return -tmp + logl(2.50662827465L * series);
}

static long double binomial_ln(int successes, int trials)
{
    return factorial_ln(trials) - factorial_ln(successes) - factorial_ln(trials - successes)
        - (long double)trials * logl(2.0L);
}

static long double outside_log_probability(const observation_t *observation)
{
    long double base_error = pow(10.0, -(double)observation->base_quality / 10.0);
    long double mapping_error = pow(10.0, -(double)observation->mapping_quality / 10.0);
    return logl(1.0L - (1.0L - base_error) * (1.0L - mapping_error));
}

static balance_t allele_balance(const site_t *site, int allele)
{
    balance_t balance = {0};
    size_t index;
    for (index = 0; index < site->count; ++index) {
        const observation_t *observation = &site->items[index];
        int placed_left;
        if (base_index((char)observation->base) != allele) {
            continue;
        }
        ++balance.count;
        if (observation->forward) {
            ++balance.forward;
        }
        placed_left = observation->bases_left >= observation->bases_right;
        if (placed_left) {
            ++balance.placed_left;
        }
        if ((placed_left && observation->forward) || (!placed_left && !observation->forward)) {
            ++balance.placed_start;
        }
    }
    return balance;
}

static long double observation_prior(balance_t balance)
{
    return binomial_ln(balance.forward, balance.count)
        + binomial_ln(balance.placed_left, balance.count)
        + binomial_ln(balance.placed_start, balance.count);
}

static long double logsumexp(const long double *values, int count)
{
    long double maximum = values[0];
    long double sum = 0.0L;
    int index;
    for (index = 1; index < count; ++index) {
        if (values[index] > maximum) {
            maximum = values[index];
        }
    }
    for (index = 0; index < count; ++index) {
        sum += expl(values[index] - maximum);
    }
    return maximum + logl(sum);
}

static void emit_header(const options_t *options, const reference_t *reference)
{
    size_t index;
    printf("##fileformat=VCFv4.2\n");
    printf("##source=bwa-snv-call-0.1\n");
    for (index = 0; index < reference->count; ++index) {
        printf("##contig=<ID=%s,length=%zu>\n", reference->items[index].name,
            reference->items[index].length);
    }
    printf("##INFO=<ID=DP,Number=1,Type=Integer,Description=\"Read depth\">\n");
    printf("##FORMAT=<ID=GT,Number=1,Type=String,Description=\"Genotype\">\n");
    printf("##FORMAT=<ID=DP,Number=1,Type=Integer,Description=\"Read depth\">\n");
    printf("##FORMAT=<ID=AD,Number=R,Type=Integer,Description=\"Allele depths\">\n");
    printf("##FORMAT=<ID=GL,Number=G,Type=Float,Description=\"Genotype likelihoods\">\n");
    printf("##FORMAT=<ID=GQ,Number=1,Type=Float,Description=\"Genotype quality\">\n");
    printf("#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\t%s\n", options->sample);
}

static void emit_site(const options_t *options, const contig_t *contig, size_t position)
{
    const long double contamination = 10e-9L;
    const long double read_dependence = 0.9L;
    const site_t *site = &contig->sites[position];
    int counts[4] = {0, 0, 0, 0};
    int reference_allele = base_index(contig->sequence[position]);
    int alternate_allele = -1;
    int reference_count;
    int alternate_count;
    int depth;
    int genotype_count = options->ploidy == 1 ? 2 : 3;
    int genotype_ref_copies[3] = {2, 1, 0};
    int genotype_alt_copies[3] = {0, 1, 2};
    long double likelihood[3] = {0, 0, 0};
    long double posterior[3] = {0, 0, 0};
    long double normalized_gl[3] = {0, 0, 0};
    long double normalizer;
    long double quality;
    long double genotype_quality;
    balance_t ref_balance;
    balance_t alt_balance;
    int call = 0;
    size_t index;
    int genotype;

    if (reference_allele < 0 || site->count == 0) {
        return;
    }
    for (index = 0; index < site->count; ++index) {
        int allele = base_index((char)site->items[index].base);
        if (allele >= 0) {
            ++counts[allele];
        }
    }
    for (genotype = 0; genotype < 4; ++genotype) {
        if (genotype != reference_allele
            && (alternate_allele < 0 || counts[genotype] > counts[alternate_allele])) {
            alternate_allele = genotype;
        }
    }
    reference_count = counts[reference_allele];
    alternate_count = counts[alternate_allele];
    depth = (int)site->count;
    if (alternate_count < options->min_alternate_count || depth == 0
        || (long double)alternate_count / (long double)depth < options->min_alternate_fraction) {
        return;
    }

    if (options->ploidy == 1) {
        genotype_ref_copies[0] = 1;
        genotype_alt_copies[0] = 0;
        genotype_ref_copies[1] = 0;
        genotype_alt_copies[1] = 1;
    }
    for (genotype = 0; genotype < genotype_count; ++genotype) {
        long double outside_sum = 0.0L;
        int outside_count = 0;
        for (index = 0; index < site->count; ++index) {
            const observation_t *observation = &site->items[index];
            int allele = base_index((char)observation->base);
            int copies = allele == reference_allele ? genotype_ref_copies[genotype]
                : allele == alternate_allele ? genotype_alt_copies[genotype] : 0;
            if (copies == 0) {
                outside_sum += outside_log_probability(observation);
                ++outside_count;
            } else {
                long double sampling = (long double)copies / (long double)options->ploidy;
                if (sampling == 1.0L) {
                    sampling = 1.0L - contamination;
                } else if (allele == reference_allele) {
                    sampling *= (0.5L + contamination) / 0.5L;
                } else {
                    sampling *= (0.5L - contamination) / 0.5L;
                }
                likelihood[genotype] += logl(sampling);
            }
        }
        if (outside_count > 1) {
            outside_sum *= (1.0L + (long double)(outside_count - 1) * read_dependence)
                / (long double)outside_count;
        }
        likelihood[genotype] += outside_sum;
    }

    ref_balance = allele_balance(site, reference_allele);
    alt_balance = allele_balance(site, alternate_allele);
    if (options->ploidy == 1) {
        posterior[0] = likelihood[0] + observation_prior(ref_balance);
        posterior[1] = likelihood[1] + observation_prior(alt_balance);
    } else {
        long double hom_ewens = -logl(options->theta + 1.0L);
        long double het_ewens = logl(options->theta) - logl(options->theta + 1.0L);
        posterior[0] = likelihood[0] + observation_prior(ref_balance) + hom_ewens;
        posterior[2] = likelihood[2] + observation_prior(alt_balance) + hom_ewens;
        posterior[1] = likelihood[1] + observation_prior(ref_balance)
            + observation_prior(alt_balance)
            + binomial_ln(reference_count, reference_count + alternate_count) + het_ewens;
    }
    normalizer = logsumexp(posterior, genotype_count);
    for (genotype = 1; genotype < genotype_count; ++genotype) {
        if (likelihood[genotype] > likelihood[call]) {
            call = genotype;
        }
    }
    for (genotype = 0; genotype < genotype_count; ++genotype) {
        normalized_gl[genotype] = (likelihood[genotype] - likelihood[call]) / logl(10.0L);
    }
    quality = -10.0L * (posterior[0] - normalizer) / logl(10.0L);
    genotype_quality = -10.0L * log10l(-expm1l(posterior[call] - normalizer));

    printf("%s\t%zu\t.\t%c\t%c\t%.6Lg\t.\tDP=%d\tGT:DP:AD:GL:GQ\t",
        contig->name, position + 1, "ACGT"[reference_allele], "ACGT"[alternate_allele],
        quality, depth);
    if (options->ploidy == 1) {
        printf("%d:%d:%d,%d:%.6Lg,%.6Lg:%.6Lg\n", call, depth, reference_count,
            alternate_count, normalized_gl[0], normalized_gl[1], genotype_quality);
    } else {
        static const char *genotypes[] = {"0/0", "0/1", "1/1"};
        printf("%s:%d:%d,%d:%.6Lg,%.6Lg,%.6Lg:%.6Lg\n", genotypes[call], depth,
            reference_count, alternate_count, normalized_gl[0], normalized_gl[1],
            normalized_gl[2], genotype_quality);
    }
}

static void free_reference(reference_t *reference)
{
    size_t contig_index;
    for (contig_index = 0; contig_index < reference->count; ++contig_index) {
        contig_t *contig = &reference->items[contig_index];
        size_t site_index;
        for (site_index = 0; site_index < contig->length; ++site_index) {
            free(contig->sites[site_index].items);
        }
        free(contig->sites);
        free(contig->sequence);
        free(contig->name);
    }
    free(reference->items);
}

static int parse_integer(const char *text, const char *name)
{
    char *end = NULL;
    long value = strtol(text, &end, 10);
    if (text[0] == '\0' || end == NULL || *end != '\0' || value < 0 || value > 1000000) {
        fprintf(stderr, "snv-call: invalid %s: %s\n", name, text);
        exit(2);
    }
    return (int)value;
}

static long double parse_real(const char *text, const char *name)
{
    char *end = NULL;
    long double value = strtold(text, &end);
    if (text[0] == '\0' || end == NULL || *end != '\0' || !isfinite((double)value)) {
        fprintf(stderr, "snv-call: invalid %s: %s\n", name, text);
        exit(2);
    }
    return value;
}

static void usage(FILE *stream)
{
    fprintf(stream,
        "Usage: bwa snv-call -f REF -s SAMPLE -p 1|2 [options] INPUT.sam\n"
        "  --min-base-quality INT\n"
        "  --min-mapping-quality INT\n"
        "  --min-alternate-count INT\n"
        "  --min-alternate-fraction FLOAT\n"
        "  --theta FLOAT\n");
}

int main_snv_call(int argc, char **argv)
{
    enum {
        OPT_MIN_BASE_QUALITY = 1000,
        OPT_MIN_MAPPING_QUALITY,
        OPT_MIN_ALTERNATE_COUNT,
        OPT_MIN_ALTERNATE_FRACTION,
        OPT_THETA,
    };
    static const struct option long_options[] = {
        {"min-base-quality", required_argument, NULL, OPT_MIN_BASE_QUALITY},
        {"min-mapping-quality", required_argument, NULL, OPT_MIN_MAPPING_QUALITY},
        {"min-alternate-count", required_argument, NULL, OPT_MIN_ALTERNATE_COUNT},
        {"min-alternate-fraction", required_argument, NULL, OPT_MIN_ALTERNATE_FRACTION},
        {"theta", required_argument, NULL, OPT_THETA},
        {NULL, 0, NULL, 0},
    };
    options_t options = {0};
    reference_t reference;
    int option;
    size_t contig_index;
    options.ploidy = 2;
    options.min_alternate_count = 1;
    options.theta = 0.001L;
    optind = 1;
    while ((option = getopt_long(argc, argv, "f:s:p:h", long_options, NULL)) != -1) {
        switch (option) {
        case 'f': options.reference_path = optarg; break;
        case 's': options.sample = optarg; break;
        case 'p': options.ploidy = parse_integer(optarg, "ploidy"); break;
        case OPT_MIN_BASE_QUALITY:
            options.min_base_quality = parse_integer(optarg, "minimum base quality"); break;
        case OPT_MIN_MAPPING_QUALITY:
            options.min_mapping_quality = parse_integer(optarg, "minimum mapping quality"); break;
        case OPT_MIN_ALTERNATE_COUNT:
            options.min_alternate_count = parse_integer(optarg, "minimum alternate count"); break;
        case OPT_MIN_ALTERNATE_FRACTION:
            options.min_alternate_fraction = parse_real(optarg, "minimum alternate fraction"); break;
        case OPT_THETA: options.theta = parse_real(optarg, "theta"); break;
        case 'h': usage(stdout); return 0;
        default: usage(stderr); return 2;
        }
    }
    if (options.reference_path == NULL || options.sample == NULL || optind + 1 != argc
        || (options.ploidy != 1 && options.ploidy != 2)
        || options.min_alternate_fraction < 0.0L || options.min_alternate_fraction > 1.0L
        || options.theta <= 0.0L) {
        usage(stderr);
        return 2;
    }
    options.sam_path = argv[optind];
    reference = load_reference(options.reference_path);
    load_sam(&reference, &options);
    emit_header(&options, &reference);
    for (contig_index = 0; contig_index < reference.count; ++contig_index) {
        size_t position;
        for (position = 0; position < reference.items[contig_index].length; ++position) {
            emit_site(&options, &reference.items[contig_index], position);
        }
    }
    free_reference(&reference);
    return 0;
}
