/*
 * Authoring probe for the one-sample, two-allele FreeBayes posterior.
 *
 * This is a clean-room scalar transcription used to check our understanding
 * of the locked executable.  It is intentionally limited to the fixed-start,
 * forward-strand fixtures produced by make_reference_probe.py and is not the
 * task solution.
 */

#include <float.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>

static long double fb_gammaln(long double x)
{
    static const long double cofactors[] = {
        76.18009173L,
        -86.50532033L,
        24.01409822L,
        -1.231739516L,
        0.120858003e-2L,
        -0.536382e-5L,
    };
    long double x1 = x - 1.0L;
    long double tmp = x1 + 5.5L;
    long double ser = 1.0L;
    int index;

    tmp -= (x1 + 0.5L) * logl(tmp);
    for (index = 0; index < 6; ++index) {
        x1 += 1.0L;
        ser += cofactors[index] / x1;
    }
    return -tmp + logl(2.50662827465L * ser);
}

static long double factorial_ln(int value)
{
    if (value < 0) {
        return -1.0L;
    }
    if (value == 0) {
        return 0.0L;
    }
    return fb_gammaln((long double)value + 1.0L);
}

static long double binomial_ln(int successes, int trials)
{
    return factorial_ln(trials) - factorial_ln(successes)
        - factorial_ln(trials - successes) - (long double)trials * logl(2.0L);
}

static long double ewens_ln(int heterozygous, long double theta)
{
    if (heterozygous) {
        return logl(theta) - logl(theta + 1.0L);
    }
    return -logl(theta + 1.0L);
}

static long double logsumexp3(const long double values[3])
{
    long double maximum = values[0];
    double sum;
    int index;
    for (index = 1; index < 3; ++index) {
        if (values[index] > maximum) {
            maximum = values[index];
        }
    }
    /* Utility.cpp converts each BigFloat input and result through double. */
    sum = exp((double)(values[0] - maximum))
        + exp((double)(values[1] - maximum))
        + exp((double)(values[2] - maximum));
    return (double)maximum + log(sum);
}

int main(int argc, char **argv)
{
    const long double read_dependence = 0.9L;
    const long double contamination = 10e-9L;
    long double likelihood[3];
    long double posterior[3];
    long double gl[3];
    long double normalizer;
    long double theta;
    long double base_error;
    long double map_error;
    long double outside_error;
    int reference_count;
    int alternate_count;
    int depth;
    int base_quality;
    int mapping_quality;
    int call = 0;
    int index;

    if (argc != 7) {
        fprintf(stderr, "usage: %s REF ALT BQ MQ THETA PLOIDY\n", argv[0]);
        return 2;
    }
    reference_count = atoi(argv[1]);
    alternate_count = atoi(argv[2]);
    base_quality = atoi(argv[3]);
    mapping_quality = atoi(argv[4]);
    theta = strtold(argv[5], NULL);
    if (atoi(argv[6]) != 2) {
        fprintf(stderr, "this authoring probe currently covers diploid input only\n");
        return 2;
    }
    depth = reference_count + alternate_count;
    base_error = powl(10.0L, -(long double)base_quality / 10.0L);
    map_error = powl(10.0L, -(long double)mapping_quality / 10.0L);
    outside_error = 1.0L - (1.0L - base_error) * (1.0L - map_error);

    likelihood[0] = (long double)reference_count * logl(1.0L - contamination);
    likelihood[2] = (long double)alternate_count * logl(1.0L - contamination);
    if (alternate_count > 0) {
        likelihood[0] += (long double)alternate_count * logl(outside_error)
            * (1.0L + (long double)(alternate_count - 1) * read_dependence)
            / (long double)alternate_count;
    }
    if (reference_count > 0) {
        likelihood[2] += (long double)reference_count * logl(outside_error)
            * (1.0L + (long double)(reference_count - 1) * read_dependence)
            / (long double)reference_count;
    }
    likelihood[1] = (long double)reference_count * logl(0.5L + contamination)
        + (long double)alternate_count * logl(0.5L - contamination);

    /* All observations in this probe are forward, placed-left and at-start. */
    posterior[0] = likelihood[0] + 3.0L * binomial_ln(reference_count, reference_count)
        + ewens_ln(0, theta);
    posterior[2] = likelihood[2] + 3.0L * binomial_ln(alternate_count, alternate_count)
        + ewens_ln(0, theta);
    posterior[1] = likelihood[1]
        + 3.0L * (binomial_ln(reference_count, reference_count)
            + binomial_ln(alternate_count, alternate_count))
        + binomial_ln(reference_count, depth) + ewens_ln(1, theta);

    normalizer = logsumexp3(posterior);
    for (index = 1; index < 3; ++index) {
        if (likelihood[index] > likelihood[call]) {
            call = index;
        }
    }
    for (index = 0; index < 3; ++index) {
        gl[index] = (likelihood[index] - likelihood[call]) / logl(10.0L);
    }

    printf("GL=%.12Lg,%.12Lg,%.12Lg\n", gl[0], gl[1], gl[2]);
    printf("QUAL=%.12Lg\n", -10.0L * (posterior[0] - normalizer) / logl(10.0L));
    printf("GQ=%.12Lg\n", -10.0L * log10l(-expm1l(posterior[call] - normalizer)));
    printf("CALL=%d\n", call);
    return 0;
}
