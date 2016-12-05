#!/usr/bin/python

'''
Run Maker
Author Byoungnam Min on May 7, 2015
 - Update on Sep 16, 2015: make multiple est libraries available
 - Update on Nov 11, 2015: Training maker
'''

# Import modules
import sys
import os
import re
from shutil import copyfile
from glob import glob
from argparse import ArgumentParser

# Get Logging
this_path = os.path.realpath(__file__)
this_dir = os.path.dirname(this_path)
sys.path.append(this_dir)
from set_logging import set_logging

# Parameters
software = 'gpre_maker'
gmes_prefix = 'gpre_genemark'


def main(argv):
    optparse_usage = (
        'run_maker.py -i <input_fasta> -r <root_dir> -p <project_name>'
        ' -P <protein_db_fastas> -c <num_cores> -R <repeat_model>'
        ' -e <est_files> -C <config_file>'
    )
    parser = ArgumentParser(usage=optparse_usage)
    parser.add_argument(
        "-i", "--input_fasta", dest="input_fasta", nargs=1,
        help="Input genome sequence in FASTA format"
    )
    parser.add_argument(
        "-r", "--root_dir", dest="root_dir", nargs=1,
        help="Resulting files will be generated here"
    )
    parser.add_argument(
        "-a", "--augustus_species", dest="augustus_species", nargs=1,
        help='"augustus --species=help" would be helpful'
    )
    parser.add_argument(
        "-p", "--project_name", dest="project_name", nargs=1,
        help="Output prefix for resulting files without space"
    )
    parser.add_argument(
        "-P", "--protein_db_fastas", dest="protein_db_fastas", nargs=1,
        help="Protein db in FASTA foramt. It could be SwissProt "
        "or UniProt database"
    )
    parser.add_argument(
        "-c", "--num_cores", dest="num_cores", nargs=1,
        help="Number of cores to be used"
    )
    parser.add_argument(
        '-R', '--repeat_model', dest="repeat_model", nargs=1,
        help="Custom repeat model by RepeatModeler"
    )
    parser.add_argument(
        '-e', '--est_files', dest="est_files", nargs='*',
        help="Multiple EST data if available"
    )
    parser.add_argument(
        "-C", "--config_file", dest="config_file", nargs=1,
        help="Config file generated by check_dependencies.py"
    )

    args = parser.parse_args()
    if args.input_fasta:
        input_fasta = os.path.abspath(args.input_fasta[0])
    else:
        print '[ERROR] Please provide INPUT FASTA'
        sys.exit(2)

    if args.root_dir:
        root_dir = os.path.abspath(args.root_dir[0])
    else:
        print '[ERROR] Please provide ROOT DIRECTORY'
        sys.exit(2)

    if args.augustus_species:
        augustus_species = args.augustus_species[0]
    else:
        print '[ERROR] Please provide AUGUSTUS SPECIES'
        sys.exit(2)

    if args.project_name:
        project_name = args.project_name[0]
    else:
        print '[ERROR] Please provide PROJECT NAME'
        sys.exit(2)

    if args.protein_db_fastas:
        protein_db_fastas = [
            os.path.abspath(x) for x in args.protein_db_fastas
        ]
    else:
        print '[ERROR] Please provide PROTEIN DB FASTA FILES'
        sys.exit(2)

    if args.num_cores:
        num_cores = args.num_cores[0]
    else:
        num_cores = 1

    if args.repeat_model:
        repeat_model = os.path.abspath(args.repeat_model[0])
    else:
        print '[ERROR] Please provide REPEAT MODEL'
        sys.exit(2)

    if args.est_files:
        est_files = [os.path.abspath(x) for x in args.est_files]
    else:
        est_files = ['']

    if args.config_file:
        config_file = os.path.abspath(args.config_file[0])
    else:
        print '[ERROR] Please provide CONFIG FILE'
        sys.exit(2)

    # Create necessary directory
    create_dir(root_dir)

    # Set logging
    log_file = os.path.join(
        root_dir, 'logs', 'pipeline', 'run_maker.log'
    )
    global logger_time, logger_txt
    logger_time, logger_txt = set_logging(log_file)

    maker_bin, genemark_bin = parse_config(config_file)

    # Run Maker on each EST file
    all_gff_file = ''
    for est_file in est_files:
        # Create directory
        est_prefix = (os.path.basename(est_file)
                        .split('.')[0]
                        .replace('Trinity_', ''))
        est_dir = os.path.join(root_dir, software, est_prefix)
        if not glob(est_dir):
            os.mkdir(est_dir)

        # Check maker is already done
        run_flag_run1 = check_maker_finished(
            root_dir, input_fasta, '1', est_prefix
        )

        # Run Maker batch
        logger_time.debug('START running Maker run1')
        if run_flag_run1:
            run_maker_batch(
                input_fasta, root_dir, augustus_species, protein_db_fastas,
                num_cores, repeat_model, est_file, all_gff_file, maker_bin
            )
        else:
            logger_txt.debug('Running Maker has already been finished')
        logger_time.debug('DONE  running Maker run1')

        # Train run1 & run Maker run2
        all_gff_file_run1 = collect_result(
            input_fasta, root_dir, project_name, '1', est_prefix
        )
        logger_time.debug('START training run1 & running maker run2')
        snap_hmm_file_run1 = train_snap(
            root_dir, all_gff_file_run1, '1', est_prefix, maker_bin
        )
        run_flag_run2 = check_maker_finished(
            root_dir, input_fasta, '2', est_prefix
        )
        if run_flag_run2:
            run_maker_trained(
                input_fasta, root_dir, augustus_species, num_cores,
                snap_hmm_file_run1, all_gff_file_run1, '2', est_prefix,
                maker_bin
            )
        else:
            logger_txt.debug('Running Maker has already been finished')
        logger_time.debug('DONE  training run1 & running maker run2')

        # Train run2 & run Maker run3
        all_gff_file_run2 = collect_result(
            input_fasta, root_dir, project_name, '2', est_prefix
        )
        logger_time.debug('START training run2 & running maker run3')
        snap_hmm_file_run2 = train_snap(
            root_dir, all_gff_file_run2, '2', est_prefix, maker_bin
        )
        run_flag_run3 = check_maker_finished(
            root_dir, input_fasta, '3', est_prefix
        )
        if run_flag_run3:
            run_maker_trained(
                input_fasta, root_dir, augustus_species, num_cores,
                snap_hmm_file_run2, all_gff_file_run2, '3', est_prefix,
                maker_bin
            )
        else:
            logger_txt.debug('Running Maker has already been finished')
        logger_time.debug('DONE  training run2 & running maker run3')

        # Now, for final run, get masked assembly and get GeneMark hmm model
        masked_assembly = get_masked_asm(root_dir, est_files)

        # Run gmes or gmsn
        eukgmhmmfile = run_gmes(
            masked_assembly, num_cores, root_dir, genemark_bin
        )

        # Train run3 & run Maker run4
        all_gff_file_run3 = collect_result(
            input_fasta, root_dir, project_name, '3', est_prefix
        )
        logger_time.debug('START training run3 & running maker run4')
        snap_hmm_file_run3 = train_snap(
            root_dir, all_gff_file_run3, '3', est_prefix, maker_bin
        )
        run_flag_run4 = check_maker_finished(
            root_dir, input_fasta, '4', est_prefix
        )
        if run_flag_run4:
            run_maker_trained(
                input_fasta, root_dir, augustus_species, num_cores,
                snap_hmm_file_run3, all_gff_file_run3, '4', est_prefix,
                maker_bin, eukgmhmmfile
            )
        else:
            logger_txt.debug('Running Maker has already been finished')
        logger_time.debug('DONE  training run3 & running maker run4')

        # Get final GFF3 & FASTA
        collect_result_final(
            input_fasta, root_dir, project_name, est_prefix
        )

        all_gff_file = collect_result(
            input_fasta, root_dir, project_name, '4', est_prefix
        )


def import_file(input_file):
    with open(input_file) as f_in:
        txt = (line.rstrip() for line in f_in)
        txt = list(line for line in txt if line)
    return txt


def replace(fname, srcstr, deststr):
    f = open(fname)
    txt = f.read()
    txt = re.subn(r'\n%s.+' % srcstr, '\n%s' % deststr, txt)[0]
    f = open(fname, 'w')
    f.write(txt)
    f.close()


def create_dir(root_dir):
    software_dir = os.path.join(root_dir, software)
    if not glob(software_dir):
        os.mkdir(software_dir)

    log_dir = os.path.join(root_dir, 'logs')
    if not glob(log_dir):
        os.mkdir(log_dir)

    log_software_dir = os.path.join(root_dir, 'logs', software)
    if not glob(log_software_dir):
        os.mkdir(log_software_dir)

    log_pipeline_dir = os.path.join(root_dir, 'logs', 'pipeline')
    if not glob(log_pipeline_dir):
        os.mkdir(log_pipeline_dir)


def parse_config(config_file):
    config_txt = import_file(config_file)
    for line in config_txt:
        if line.startswith('MAKER_PATH='):
            maker_bin = line.replace('MAKER_PATH=', '')
        elif line.startswith('GENEMARK_PATH='):
            genemark_bin = line.replace('GENEMARK_PATH=', '')
    return maker_bin, genemark_bin


def check_maker_finished(root_dir, input_fasta, version, prefix):
    # For first run
    index_log_file = glob(os.path.join(
        root_dir, software, prefix,
        'maker_run%s/*output/*master_datastore_index.log' % version)
    )

    if not index_log_file:
        return True

    index_log = import_file(index_log_file[0])
    finished_scaffolds = []
    for line in index_log:
        line_split = line.split('\t')
        finish_tag = line_split[2]
        if finish_tag != 'FINISHED':
            continue

        finished_scaffold = line_split[0]
        finished_scaffolds.append(finished_scaffold)

    fasta = import_file(input_fasta)
    fasta_scaffolds = []
    for line in fasta:
        if not re.search('^>', line):
            continue
        fasta_scaffold = line.split(' ')[0].replace('>', '')
        fasta_scaffolds.append(fasta_scaffold)

    if finished_scaffolds == fasta_scaffolds:
        return False
    else:
        return True


def run_gmes(
    masked_assembly, num_cores, root_dir, genemark_bin
):

    # Create directory
    gmes_dir = os.path.join(root_dir, gmes_prefix)
    if not glob(gmes_dir):
        os.mkdir(gmes_dir)

    log_dir = os.path.join(root_dir, 'logs', gmes_prefix)
    if not glob(log_dir):
        os.mkdir(log_dir)

    # Run gm_es.pl
    gmes_path = os.path.join(root_dir, gmes_prefix)
    output_gmes = os.path.join(gmes_path, 'output/gmhmm.mod')
    log_file = os.path.join(root_dir, 'logs', gmes_prefix, 'gmes.log')

    logger_time.debug('START ruuning gmes to build hmm')
    if not glob(output_gmes):
        os.chdir(gmes_path)
        command = (
            '%s --ES --fungus --cores %s --sequence %s '
            '--soft_mask 1 > %s' % (
                genemark_bin, num_cores, masked_assembly, log_file
            )
        )
        logger_txt.debug('[Run] %s' % (command))
        os.system(command)
    else:
        logger_txt.debug('GMES has already been finished')
    logger_time.debug('DONE  running gmes to build hmm')

    return output_gmes


def run_maker_batch(
    input_fasta, root_dir, augustus_species, protein_db_fastas,
    num_cores, repeat_model, est_file, all_gff_file, maker_bin
):
    est_prefix = (os.path.basename(est_file)
                    .split('.')[0]
                    .replace('Trinity_', ''))

    # Change directory
    maker_run1_dir = os.path.join(root_dir, software, est_prefix, 'maker_run1')
    if not glob(maker_run1_dir):
        os.mkdir(maker_run1_dir)

    # Change directory
    os.chdir(maker_run1_dir)

    # Make CTL files
    os.environ["PATH"] += os.path.join(
        this_dir, 'external/exonerate-2.2.0-x86_64/bin/exonerate'
    )
    os.system('%s -CTL' % (maker_bin))

    # Editting maker_opts.ctl - general
    replace('maker_opts.ctl', 'genome= ', 'genome=%s ' % input_fasta)
    replace('maker_opts.ctl', 'protein=  ', 'protein=%s ' % ','.join(
        protein_db_fastas)
    )
    replace('maker_opts.ctl', 'cpus=1', 'cpus=%s' % num_cores)

    # For fungal genome
    replace('maker_opts.ctl', 'split_hit=', 'split_hit=5000')
    replace('maker_opts.ctl', 'single_exon=', 'single_exon=1')
    replace('maker_opts.ctl', 'single_length=', 'single_length=150')
    replace('maker_opts.ctl', 'correct_est_fusion=', 'correct_est_fusion=1')

    # If EST is provided
    if est_file != '':
        replace('maker_opts.ctl', "est= ", "est=%s " % (est_file))
        replace('maker_opts.ctl', "est2genome=0 ", "est2genome=1 ")

    # Set repeat model
    replace(
        'maker_opts.ctl', 'model_org=all', 'model_org='
    )

    # Run faster feed aligned transcripts, proteins, repeat masking
    if all_gff_file:
        replace(
            'maker_opts.ctl', 'maker_gff= ', 'maker_gff=%s ' % (all_gff_file)
        )
        replace('maker_opts.ctl', 'protein_pass=0', 'protein_pass=1')
        replace('maker_opts.ctl', 'rm_pass=0', 'rm_pass=1')
        replace(
            'maker_opts.ctl', 'repeat_protein=', 'repeat_protein='
        )

    else:
        replace(
            'maker_opts.ctl', 'rmlib= ', 'rmlib=%s' % (repeat_model)
        )

    # Run maker
    maker_log = os.path.join(
        root_dir, 'logs', 'gpre_maker', 'maker_%s_run1.log' % (est_prefix)
    )
    command = '%s -fix_nucleotides > %s 2>&1' % (maker_bin, maker_log)
    logger_txt.debug('[Run] %s' % (command))
    os.system(command)


def run_maker_trained(
    input_fasta, root_dir, augustus_species, num_cores, snap_hmm_file,
    all_gff_file, version, prefix, maker_bin, eukgmhmmfile=None
):

    # Create directory
    maker_run_dir = os.path.join(
        root_dir, software, prefix, 'maker_run%s' % (version)
    )

    if not glob(maker_run_dir):
        os.mkdir(maker_run_dir)

    # Change directory
    os.chdir(maker_run_dir)

    # Make CTL files
    os.system('%s -CTL' % (maker_bin))

    # Editting maker_opts.ctl - general
    replace('maker_opts.ctl', 'genome= ', 'genome=%s ' % input_fasta)
    replace('maker_opts.ctl', 'cpus=1', 'cpus=%s' % num_cores)

    # For fungal genome
    replace('maker_opts.ctl', 'split_hit=', 'split_hit=5000')
    replace('maker_opts.ctl', 'single_exon=', 'single_exon=1')
    replace('maker_opts.ctl', 'single_length=', 'single_length=150')
    replace('maker_opts.ctl', 'correct_est_fusion=', 'correct_est_fusion=1')

    # Remove repeat org
    replace(
        'maker_opts.ctl', 'model_org=all', 'model_org='
    )
    replace(
        'maker_opts.ctl', 'repeat_protein=', 'repeat_protein='
    )

    # Supply SNAP HMM v1
    replace('maker_opts.ctl', 'snaphmm= ', 'snaphmm=%s ' % (snap_hmm_file))

    # Run faster feed aligned transcripts, proteins, repeat masking
    replace('maker_opts.ctl', 'maker_gff= ', 'maker_gff=%s ' % (all_gff_file))
    replace('maker_opts.ctl', 'est_pass=0', 'est_pass=1')
    replace('maker_opts.ctl', 'protein_pass=0', 'protein_pass=1')
    replace('maker_opts.ctl', 'rm_pass=0', 'rm_pass=1')

    # Last run, keep_preds=1
    if version == '4':
        replace('maker_opts.ctl', 'keep_preds=0', 'keep_preds=1')

        # Set AUGUSTUS species
        replace(
            'maker_opts.ctl', 'augustus_species= ', 'augustus_species=%s ' % (
                augustus_species)
        )

        # Set gmhmm
        replace('maker_opts.ctl', 'gmhmm= ', 'gmhmm=%s ' % (eukgmhmmfile))

    # Run maker
    maker_log = os.path.join(
        root_dir, 'logs', 'gpre_maker',
        'maker_%s_run%s.log' % (prefix, version)
    )
    command = '%s -fix_nucleotides > %s 2>&1' % (maker_bin, maker_log)
    logger_txt.debug('[Run] %s' % (command))
    os.system(command)


def collect_result(input_fasta, root_dir, project_name, version, prefix):
    maker_run_dir = os.path.join(
        root_dir, software, prefix, 'maker_run%s' % (version)
    )
    input_prefix = (
        os.path.basename(input_fasta)
        .replace('.fasta', '')
        .replace('.fna', '')
        .replace('.fa', '')
    )
    index_file = os.path.join(
        maker_run_dir,
        '%s.maker.output/%s_master_datastore_index.log' % (
            input_prefix, input_prefix
        )
    )

    # Change directory to maker_run_dir
    os.chdir(maker_run_dir)
    command = 'gff3_merge -d %s' % (index_file)
    os.system(command)

    all_gff_file = '%s.all.gff' % (input_prefix)
    all_gff_file_abs = os.path.abspath(all_gff_file)

    os.chdir(root_dir)

    return all_gff_file_abs


def collect_result_final(input_fasta, root_dir, project_name, prefix):
    maker_run_dir = os.path.join(root_dir, software, prefix, 'maker_run4')
    input_prefix = (
        os.path.basename(input_fasta)
        .replace('.fasta', '')
        .replace('.fna', '')
        .replace('.fa', '')
    )
    index_file = os.path.join(
        maker_run_dir,
        '%s.maker.output/%s_master_datastore_index.log' % (
            input_prefix, input_prefix
        )
    )

    # Change directory to maker_run_dir
    os.chdir(maker_run_dir)
    command1 = 'gff3_merge -g -n -d %s' % (index_file)
    os.system(command1)

    # Collect FASTA, too
    command2 = 'fasta_merge -d %s' % (index_file)
    os.system(command2)

    # Copy to maker root directory
    maker_root = os.path.join(root_dir, 'gpre_maker', prefix)
    merged_gff3 = os.path.join(
        maker_root, 'maker_run4', '%s.all.gff' % (input_prefix)
    )
    merged_faa = os.path.join(
        maker_root, 'maker_run4',
        '%s.all.maker.proteins.fasta' % (input_prefix)
    )
    output_gff3 = os.path.join(maker_root, 'maker_%s.gff3' % (prefix))
    output_faa = os.path.join(maker_root, 'maker_%s.faa' % (prefix))

    copyfile(merged_gff3, output_gff3)
    copyfile(merged_faa, output_faa)

    os.chdir(root_dir)


def train_snap(root_dir, all_gff_file, version, prefix, maker_bin):
    maker_run_dir = os.path.join(
        root_dir, software, prefix, 'maker_run%s' % (version)
    )
    maker_dir = os.path.dirname(maker_bin)
    maker2zff_bin = os.path.join(maker_dir, 'maker2zff')
    fathom_bin = os.path.join(maker_dir, '../exe/fathom')
    forge_bin = os.path.join(maker_dir, '../exe/forge')
    hmm_assembler_bin = os.path.join(maker_dir, '../exe/hmm-assembler.pl')

    # Change directory into Maker run1 directory
    os.chdir(maker_run_dir)
    if not os.path.exists('snp_training'):
        os.makedirs('snp_training')
    os.chdir('snp_training')

    snap_hmm_file = os.path.abspath('snap_hmm_v%s.hmm' % (version))
    if not os.path.exists(snap_hmm_file):
        # Run maker2zff to select a subset of gene models for training
        command1 = '%s -n %s' % (maker2zff_bin, all_gff_file)
        logger_txt.debug('[Run] %s' % (command1))
        os.system(command1)

        # It generates genome.dna and genome.ann
        # split the annotations into four categories: unique genes, warnings,
        # alternative spliced genes, overlapping genes, and errors
        command2 = '%s -categorize 1000 genome.ann genome.dna' % (fathom_bin)
        logger_txt.debug('[Run] %s' % (command2))
        os.system(command2)

        # Export the genes
        command3 = '%s -export 1000 -plus uni.ann uni.dna' % (fathom_bin)
        logger_txt.debug('[Run] %s' % (command3))
        os.system(command3)

        # Create directory
        if not os.path.exists('parameters'):
            os.makedirs('parameters')

        # Change directory
        os.chdir('parameters')

        # Generate the new parameters with forge
        command4 = '%s ../export.ann ../export.dna' % (forge_bin)
        logger_txt.debug('[Run] %s' % (command4))
        os.system(command4)

        # Generate the new HMM
        os.chdir('..')
        command5 = '%s snap_hmm_v%s parameters > snap_hmm_v%s.hmm' % (
            hmm_assembler_bin, version, version
        )
        logger_txt.debug('[Run] %s' % (command5))
        os.system(command5)
    else:
        logger_txt.debug("SNAP training has been alread finished for %s" % (
            os.path.basename(snap_hmm_file)))

    os.chdir(root_dir)

    return snap_hmm_file


def get_masked_asm(root_dir, est_files):
    est_prefix_first = (os.path.basename(est_files[0])
                        .split('.')[0]
                        .replace('Trinity_', ''))

    maker_run_dir = os.path.join(
        root_dir, software, est_prefix_first, 'maker_run3'
    )
    masked_asm_path = os.path.join(
        maker_run_dir, '*/*/*/*/*/*/query.masked.fasta'
    )
    # masked_asm_files = glob(masked_asm_path)
    masked_asm = os.path.join(root_dir, software, 'masked_assembly.fasta')
    command = '(ls %s | xargs cat) > %s' % (masked_asm_path, masked_asm)
    logger_txt.debug('[Run] %s' % (command))
    os.system(command)

    return masked_asm


if __name__ == "__main__":
    main(sys.argv[1:])
