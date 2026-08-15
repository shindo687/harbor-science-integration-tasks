import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Base64;
import java.util.List;

import org.broadinstitute.hellbender.tools.walkers.variantutils.HaplotypeCompareVariants;

public final class HaplotypeCompareHarness {
    private HaplotypeCompareHarness() {
    }

    private static String decode(final String value) {
        return new String(Base64.getUrlDecoder().decode(value), StandardCharsets.UTF_8);
    }

    private static String encode(final String value) {
        return Base64.getUrlEncoder().withoutPadding()
                .encodeToString(value.getBytes(StandardCharsets.UTF_8));
    }

    public static void main(final String[] args) throws Exception {
        try {
            final BufferedReader input = new BufferedReader(
                    new InputStreamReader(System.in, StandardCharsets.UTF_8));
            final String header = input.readLine();
            if (header == null) {
                throw new IllegalArgumentException("missing request header");
            }
            final String[] headerFields = header.split("\\t", -1);
            if (headerFields.length != 3 || !"R".equals(headerFields[0])) {
                throw new IllegalArgumentException("invalid request header");
            }
            final int referenceStart = Integer.parseInt(headerFields[1]);
            final String reference = decode(headerFields[2]);
            final List<HaplotypeCompareVariants.Variant> truth = new ArrayList<>();
            final List<HaplotypeCompareVariants.Variant> query = new ArrayList<>();
            String line;
            boolean ended = false;
            while ((line = input.readLine()) != null) {
                if ("E".equals(line)) {
                    ended = true;
                    break;
                }
                final String[] fields = line.split("\\t", -1);
                if (fields.length != 6 || !("T".equals(fields[0]) || "Q".equals(fields[0]))) {
                    throw new IllegalArgumentException("invalid variant row");
                }
                final HaplotypeCompareVariants.Variant variant =
                        new HaplotypeCompareVariants.Variant(
                                decode(fields[1]), Integer.parseInt(fields[2]), decode(fields[3]),
                                decode(fields[4]), decode(fields[5]));
                ("T".equals(fields[0]) ? truth : query).add(variant);
            }
            if (!ended) {
                throw new IllegalArgumentException("unterminated request");
            }
            final HaplotypeCompareVariants.Result result =
                    HaplotypeCompareVariants.compare(reference, referenceStart, truth, query);
            System.out.println("OK");
            for (final HaplotypeCompareVariants.AlleleStatus status : result.truth) {
                System.out.println("T\t" + encode(status.id) + "\t" + status.status);
            }
            for (final HaplotypeCompareVariants.AlleleStatus status : result.query) {
                System.out.println("Q\t" + encode(status.id) + "\t" + status.status);
            }
            System.out.println("S\t" + result.truthTp + "\t" + result.queryTp + "\t"
                    + result.fp + "\t" + result.fn + "\t"
                    + Double.toString(result.precision) + "\t"
                    + Double.toString(result.recall) + "\t"
                    + Double.toString(result.f1));
        } catch (final Throwable error) {
            System.out.println("ERROR\t" + encode(error.getClass().getSimpleName()
                    + ": " + String.valueOf(error.getMessage())));
        }
    }
}
