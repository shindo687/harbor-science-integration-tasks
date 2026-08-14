#ifndef FASTTREE_ALIGN_SMALL_H
#define FASTTREE_ALIGN_SMALL_H

int AlignSmallFasta(const char *input_path,
                    const char *alignment_output_path,
                    const char *guide_tree_output_path,
                    int is_nucleotide,
                    const char *matrix_name,
                    double gap_open,
                    double gap_extend);

#endif

