/**
 * Ontology Management Commands
 */

import { Command } from 'commander';
import { createClientFromEnv } from '../api/client';
import * as colors from './colors';
import { coloredCount, separator } from './colors';
import { Table } from '../lib/table';
import { setCommandHelp } from './help-formatter';

export const ontologyCommand = setCommandHelp(
  new Command('ontology'),
  'Manage ontologies (knowledge domains)',
  'Manage ontologies (knowledge domains). Ontologies are named collections that organize concepts into knowledge domains. Each ontology groups related documents and concepts together, making it easier to organize and query knowledge by topic or project.'
)
  .alias('onto')  // Short alias
  .showHelpAfterError('(add --help for additional information)')
  .showSuggestionAfterError()
  .addCommand(
    new Command('list')
      .description('List all ontologies in the knowledge graph. Shows a table with ontology name, file count, chunk count, and concept count. Use this to get a bird\'s-eye view of all knowledge domains, verify ingestion results, and understand how knowledge is distributed.')
      .action(async () => {
        try {
          const client = createClientFromEnv();
          const result = await client.listOntologies();

          if (result.count === 0) {
            console.log(colors.status.warning('\n⚠ No ontologies found'));
            return;
          }

          console.log('\n' + colors.ui.title('📚 Ontologies in Knowledge Graph'));

          // Use Table system for consistent formatting
          const table = new Table({
            columns: [
              {
                header: 'Ontology',
                field: 'ontology',
                type: 'heading',
                width: 'flex',
                priority: 3
              },
              {
                header: 'State',
                field: 'lifecycle_state',
                type: 'text',
                width: 8,
                align: 'left'
              },
              {
                header: 'Files',
                field: 'file_count',
                type: 'count',
                width: 10,
                align: 'right'
              },
              {
                header: 'Chunks',
                field: 'source_count',
                type: 'count',
                width: 10,
                align: 'right'
              },
              {
                header: 'Concepts',
                field: 'concept_count',
                type: 'count',
                width: 12,
                align: 'right'
              }
            ]
          });

          table.print(result.ontologies.map(o => ({
            ...o,
            lifecycle_state: o.lifecycle_state ?? '—',
          })));
        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to list ontologies'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('info')
      .description('Get detailed information about a specific ontology. Shows statistics (files, chunks, concepts, evidence, relationships) and lists all source files. Use this to understand ontology composition, verify expected files are present, and troubleshoot ingestion issues.')
      .showHelpAfterError()
      .argument('<name>', 'Ontology name')
      .action(async (name) => {
        try {
          const client = createClientFromEnv();
          const info = await client.getOntologyInfo(name);

          console.log('\n' + separator());
          console.log(colors.ui.title(`📖 Ontology: ${name}`));
          console.log(separator());

          console.log('\n' + colors.stats.section('Statistics'));
          console.log(`  ${colors.stats.label('Files:')} ${coloredCount(info.statistics.file_count)}`);
          console.log(`  ${colors.stats.label('Chunks:')} ${coloredCount(info.statistics.source_count)}`);
          console.log(`  ${colors.stats.label('Concepts:')} ${coloredCount(info.statistics.concept_count)}`);
          console.log(`  ${colors.stats.label('Evidence:')} ${coloredCount(info.statistics.instance_count)}`);
          console.log(`  ${colors.stats.label('Relationships:')} ${coloredCount(info.statistics.relationship_count)}`);

          // ADR-200: Node properties
          if (info.node) {
            console.log('\n' + colors.stats.section('Graph Node'));
            console.log(`  ${colors.stats.label('ID:')} ${info.node.ontology_id}`);
            console.log(`  ${colors.stats.label('State:')} ${info.node.lifecycle_state}`);
            console.log(`  ${colors.stats.label('Epoch:')} ${coloredCount(info.node.creation_epoch)}`);
            console.log(`  ${colors.stats.label('Embedding:')} ${info.node.has_embedding ? colors.status.success('yes') : colors.status.dim('no')}`);
            if (info.node.created_by) {
              console.log(`  ${colors.stats.label('Created By:')} ${info.node.created_by}`);
            }
            if (info.node.description) {
              console.log(`  ${colors.stats.label('Description:')} ${info.node.description}`);
            }
            if (info.node.search_terms.length > 0) {
              console.log(`  ${colors.stats.label('Search terms:')} ${info.node.search_terms.join(', ')}`);
            }
          }

          if (info.files.length > 0) {
            console.log('\n' + colors.ui.header('Files'));
            console.log(separator(80, '─'));
            info.files.forEach(file => {
              console.log(`  ${colors.ui.bullet('●')} ${colors.evidence.document(file)}`);
            });
          }
          console.log('\n' + separator());
        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to get ontology info'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('files')
      .description('List files in a specific ontology with per-file statistics (chunks and concepts). Shows which files contributed most concepts and helps identify files that may need re-ingestion. Original file paths are preserved, though temporary paths may appear for text-based ingestion.')
      .showHelpAfterError()
      .argument('<name>', 'Ontology name')
      .action(async (name) => {
        try {
          const client = createClientFromEnv();
          const result = await client.getOntologyFiles(name);

          console.log('\n' + separator());
          console.log(colors.ui.title(`📁 Files in: ${name}`));
          console.log(separator());
          console.log(colors.status.success(`\n✓ Found ${result.count} files:\n`));

          result.files.forEach(file => {
            console.log(colors.evidence.document(file.file_path));
            console.log(`  ${colors.ui.key('Chunks:')} ${coloredCount(file.chunk_count)}`);
            console.log(`  ${colors.ui.key('Concepts:')} ${coloredCount(file.concept_count)}`);
            if (file.source_ids?.length) {
              console.log(`  ${colors.ui.key('Source IDs:')} ${file.source_ids.join(', ')}`);
            }
            console.log();
          });
          console.log(separator());
        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to get ontology files'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('create')
      .description('Create an ontology before ingesting any documents (ADR-200: directed growth). This pre-creates the Ontology graph node with an embedding, making the ontology discoverable in the vector space immediately. Useful for planning knowledge domains before populating them.')
      .showHelpAfterError()
      .argument('<name>', 'Ontology name')
      .option('-d, --description <text>', 'What this knowledge domain covers')
      .action(async (name, options) => {
        try {
          const client = createClientFromEnv();
          const result = await client.createOntology(name, options.description || '');

          console.log('\n' + separator());
          console.log(colors.status.success(`✓ Created ontology "${result.name}"`));
          console.log(separator());
          console.log(`  ${colors.ui.key('ID:')} ${result.ontology_id}`);
          console.log(`  ${colors.ui.key('State:')} ${result.lifecycle_state}`);
          console.log(`  ${colors.ui.key('Embedding:')} ${result.has_embedding ? colors.status.success('generated') : colors.status.dim('none')}`);
          if (result.description) {
            console.log(`  ${colors.ui.key('Description:')} ${result.description}`);
          }
          console.log('\n' + separator());
        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to create ontology'));
          const detail = error.response?.data?.detail || error.message;
          console.error(colors.status.error(detail));

          if (detail.includes('already exists')) {
            console.error(colors.status.dim('\n  Hint: Use "kg ontology info ' + name + '" to see the existing ontology'));
          }

          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('lifecycle')
      .description('Change ontology lifecycle state (ADR-200 Phase 2). States: active (normal), pinned (immune to demotion), frozen (read-only — rejects ingest and rename).')
      .showHelpAfterError()
      .argument('<name>', 'Ontology name')
      .argument('<state>', 'Target state: active, pinned, or frozen')
      .action(async (name, state) => {
        const validStates = ['active', 'pinned', 'frozen'];
        if (!validStates.includes(state)) {
          console.error(colors.status.error(`✗ Invalid state "${state}". Must be one of: ${validStates.join(', ')}`));
          process.exit(1);
        }

        try {
          const client = createClientFromEnv();
          const result = await client.updateOntologyLifecycle(name, state as any);

          console.log('\n' + separator());
          if (result.previous_state === result.new_state) {
            console.log(colors.status.dim(`  Ontology "${name}" is already ${result.new_state} (no-op)`));
          } else {
            console.log(colors.status.success(`✓ Ontology "${name}" lifecycle: ${result.previous_state} → ${result.new_state}`));
          }
          console.log(separator());
        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to update ontology lifecycle'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('rename')
      .description('Rename an ontology while preserving all its data (concepts, sources, relationships). This is a non-destructive operation useful for reorganization, archiving old ontologies, fixing typos, or improving clarity. Atomic transaction ensures all-or-nothing updates. Requires confirmation unless -y flag is used.')
      .showHelpAfterError()
      .argument('<old-name>', 'Current ontology name')
      .argument('<new-name>', 'New ontology name')
      .option('-y, --yes', 'Skip confirmation prompt')
      .action(async (oldName, newName, options) => {
        try {
          if (!options.yes) {
            console.log('\n' + separator());
            console.log(colors.status.warning('⚠️  Rename Ontology'));
            console.log(separator());
            console.log(`\nRename: ${colors.concept.label(oldName)} → ${colors.concept.label(newName)}`);
            console.log(`This will update all Source nodes in the ontology.`);
            console.log('\nUse ' + colors.ui.key('-y') + ' or ' + colors.ui.key('--yes') + ' flag to proceed\n');
            return;
          }

          const client = createClientFromEnv();
          const result = await client.renameOntology(oldName, newName);

          console.log('\n' + separator());
          console.log(colors.status.success(`✓ Renamed ontology "${result.old_name}" → "${result.new_name}"`));
          console.log(separator());
          console.log(`  ${colors.ui.key('Sources updated:')} ${coloredCount(result.sources_updated)}`);
          console.log('\n' + separator());
        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to rename ontology'));
          const detail = error.response?.data?.detail || error.message;
          console.error(colors.status.error(detail));

          // Provide helpful hints based on error
          if (detail.includes('does not exist')) {
            console.error(colors.status.dim('\n  Hint: Use "kg ontology list" to see available ontologies'));
          } else if (detail.includes('already exists')) {
            console.error(colors.status.dim('\n  Hint: Choose a different name or delete the existing ontology first'));
          }

          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('delete')
      .description('Delete an ontology and ALL its data (concepts, sources, evidence instances, relationships). This is a DESTRUCTIVE operation that CANNOT BE UNDONE. Use this to remove test data, delete old projects, or free up space. Requires --force flag for confirmation. Consider alternatives: rename to add "Archive" suffix, or export data first (future feature).')
      .showHelpAfterError()
      .argument('<name>', 'Ontology name')
      .option('-f, --force', 'Skip confirmation and force deletion')
      .action(async (name, options) => {
        try {
          if (!options.force) {
            console.log('\n' + separator());
            console.log(colors.status.warning('⚠️  WARNING: This action cannot be undone!'));
            console.log(separator());
            console.log(`\nThis will delete all data for ontology ${colors.concept.label(name)}`);
            console.log('\nUse ' + colors.ui.key('--force') + ' flag to confirm deletion\n');
            return;
          }

          const client = createClientFromEnv();
          const result = await client.deleteOntology(name, true);

          console.log('\n' + separator());
          console.log(colors.status.success(`✓ Deleted ontology "${result.ontology}"`));
          console.log(separator());
          console.log(`  ${colors.ui.key('Sources deleted:')} ${coloredCount(result.sources_deleted)}`);
          if (result.orphaned_concepts_deleted > 0) {
            console.log(`  ${colors.ui.key('Orphaned concepts cleaned:')} ${coloredCount(result.orphaned_concepts_deleted)}`);
          }
          console.log('\n' + separator());
        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to delete ontology'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  )
  // ADR-200 Phase 3a: Scoring & Breathing Control Surface
  .addCommand(
    new Command('scores')
      .description('Show cached breathing scores for an ontology (or all ontologies). Shows mass, coherence, exposure, and protection scores. Use "kg ontology score <name>" to recompute.')
      .showHelpAfterError()
      .argument('[name]', 'Ontology name (omit for all)')
      .action(async (name) => {
        try {
          const client = createClientFromEnv();

          if (name) {
            const scores = await client.getOntologyScores(name);
            console.log('\n' + separator());
            console.log(colors.ui.title(`📊 Scores: ${name}`));
            console.log(separator());
            console.log(`  ${colors.stats.label('Mass:')} ${scores.mass_score.toFixed(4)}`);
            console.log(`  ${colors.stats.label('Coherence:')} ${scores.coherence_score.toFixed(4)}`);
            console.log(`  ${colors.stats.label('Raw Exposure:')} ${scores.raw_exposure.toFixed(4)}`);
            console.log(`  ${colors.stats.label('Weighted Exposure:')} ${scores.weighted_exposure.toFixed(4)}`);
            console.log(`  ${colors.stats.label('Protection:')} ${scores.protection_score.toFixed(4)}`);
            console.log(`  ${colors.stats.label('Last Evaluated:')} epoch ${scores.last_evaluated_epoch}`);
            console.log(separator());
          } else {
            const result = await client.computeAllOntologyScores();
            console.log('\n' + colors.ui.title(`📊 All Ontology Scores (epoch ${result.global_epoch})`));

            if (result.count === 0) {
              console.log(colors.status.warning('\n⚠ No ontologies found'));
              return;
            }

            const table = new Table({
              columns: [
                { header: 'Ontology', field: 'ontology', type: 'heading', width: 'flex', priority: 3 },
                { header: 'Mass', field: 'mass_score', type: 'text', width: 8, align: 'right' },
                { header: 'Cohere', field: 'coherence_score', type: 'text', width: 8, align: 'right' },
                { header: 'Exposure', field: 'weighted_exposure', type: 'text', width: 10, align: 'right' },
                { header: 'Protect', field: 'protection_score', type: 'text', width: 10, align: 'right' },
                { header: 'Epoch', field: 'last_evaluated_epoch', type: 'count', width: 8, align: 'right' },
              ]
            });

            table.print(result.scores.map(s => ({
              ...s,
              mass_score: s.mass_score.toFixed(3),
              coherence_score: s.coherence_score.toFixed(3),
              weighted_exposure: s.weighted_exposure.toFixed(3),
              protection_score: s.protection_score.toFixed(3),
            })));
          }
        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to get ontology scores'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('score')
      .description('Recompute breathing scores for one ontology. Runs mass, coherence, exposure, and protection scoring and caches results.')
      .showHelpAfterError()
      .argument('<name>', 'Ontology name')
      .action(async (name) => {
        try {
          const client = createClientFromEnv();
          const scores = await client.computeOntologyScores(name);

          console.log('\n' + separator());
          console.log(colors.status.success(`✓ Scored ontology "${name}"`));
          console.log(separator());
          console.log(`  ${colors.stats.label('Mass:')} ${scores.mass_score.toFixed(4)}`);
          console.log(`  ${colors.stats.label('Coherence:')} ${scores.coherence_score.toFixed(4)}`);
          console.log(`  ${colors.stats.label('Raw Exposure:')} ${scores.raw_exposure.toFixed(4)}`);
          console.log(`  ${colors.stats.label('Weighted Exposure:')} ${scores.weighted_exposure.toFixed(4)}`);
          console.log(`  ${colors.stats.label('Protection:')} ${scores.protection_score.toFixed(4)}`);
          console.log(`  ${colors.stats.label('Evaluated at:')} epoch ${scores.last_evaluated_epoch}`);
          console.log(separator());
        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to score ontology'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('score-all')
      .description('Recompute breathing scores for all ontologies. Runs full scoring pipeline and caches results on each Ontology node.')
      .showHelpAfterError()
      .action(async () => {
        try {
          const client = createClientFromEnv();
          const result = await client.computeAllOntologyScores();

          console.log('\n' + colors.status.success(`✓ Scored ${result.count} ontologies (epoch ${result.global_epoch})`));

          if (result.count > 0) {
            const table = new Table({
              columns: [
                { header: 'Ontology', field: 'ontology', type: 'heading', width: 'flex', priority: 3 },
                { header: 'Mass', field: 'mass_score', type: 'text', width: 8, align: 'right' },
                { header: 'Cohere', field: 'coherence_score', type: 'text', width: 8, align: 'right' },
                { header: 'Exposure', field: 'weighted_exposure', type: 'text', width: 10, align: 'right' },
                { header: 'Protect', field: 'protection_score', type: 'text', width: 10, align: 'right' },
              ]
            });

            table.print(result.scores.map(s => ({
              ...s,
              mass_score: s.mass_score.toFixed(3),
              coherence_score: s.coherence_score.toFixed(3),
              weighted_exposure: s.weighted_exposure.toFixed(3),
              protection_score: s.protection_score.toFixed(3),
            })));
          }
        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to score all ontologies'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('candidates')
      .description('Show top concepts by degree centrality in an ontology. High-degree concepts are potential promotion candidates — they may warrant their own ontology.')
      .showHelpAfterError()
      .argument('<name>', 'Ontology name')
      .option('-l, --limit <n>', 'Max concepts', '20')
      .action(async (name, options) => {
        try {
          const client = createClientFromEnv();
          const result = await client.getOntologyCandidates(name, parseInt(options.limit));

          console.log('\n' + colors.ui.title(`🎯 Promotion Candidates: ${name}`));

          if (result.count === 0) {
            console.log(colors.status.warning('\n⚠ No concepts found'));
            return;
          }

          const table = new Table({
            columns: [
              { header: 'Concept', field: 'label', type: 'heading', width: 'flex', priority: 3 },
              { header: 'Degree', field: 'degree', type: 'count', width: 10, align: 'right' },
              { header: 'In', field: 'in_degree', type: 'count', width: 8, align: 'right' },
              { header: 'Out', field: 'out_degree', type: 'count', width: 8, align: 'right' },
            ]
          });

          table.print(result.concepts);
        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to get candidates'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('affinity')
      .description('Show cross-ontology concept overlap. Identifies which other ontologies share concepts with this one, ranked by affinity score.')
      .showHelpAfterError()
      .argument('<name>', 'Ontology name')
      .option('-l, --limit <n>', 'Max ontologies', '10')
      .action(async (name, options) => {
        try {
          const client = createClientFromEnv();
          const result = await client.getOntologyAffinity(name, parseInt(options.limit));

          console.log('\n' + colors.ui.title(`🔗 Cross-Ontology Affinity: ${name}`));

          if (result.count === 0) {
            console.log(colors.status.warning('\n⚠ No cross-ontology connections found'));
            return;
          }

          const table = new Table({
            columns: [
              { header: 'Other Ontology', field: 'other_ontology', type: 'heading', width: 'flex', priority: 3 },
              { header: 'Shared', field: 'shared_concept_count', type: 'count', width: 10, align: 'right' },
              { header: 'Total', field: 'total_concepts', type: 'count', width: 10, align: 'right' },
              { header: 'Affinity', field: 'affinity_score', type: 'text', width: 10, align: 'right' },
            ]
          });

          table.print(result.affinities.map(a => ({
            ...a,
            affinity_score: (a.affinity_score * 100).toFixed(1) + '%',
          })));
        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to get affinity'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('edges')
      .description('Show ontology-to-ontology edges (OVERLAPS, SPECIALIZES, GENERALIZES). Derived by breathing cycles or created manually.')
      .showHelpAfterError()
      .argument('<name>', 'Ontology name')
      .action(async (name) => {
        try {
          const client = createClientFromEnv();
          const result = await client.getOntologyEdges(name);

          console.log('\n' + separator());
          console.log(colors.ui.title(`Ontology Edges: ${name}`));
          console.log(separator());

          if (result.count === 0) {
            console.log(colors.status.warning('\nNo ontology edges found'));
            console.log('Edges are derived during breathing cycles or created manually.');
            return;
          }

          const table = new Table({
            columns: [
              { header: 'Type', field: 'edge_type', type: 'text', width: 14, align: 'left' },
              { header: 'Dir', field: 'direction', type: 'text', width: 10, align: 'left' },
              { header: 'Other Ontology', field: 'other_name', type: 'heading', width: 'flex', priority: 3 },
              { header: 'Score', field: 'score', type: 'text', width: 8, align: 'right' },
              { header: 'Shared', field: 'shared_concept_count', type: 'count', width: 8, align: 'right' },
              { header: 'Source', field: 'source', type: 'text', width: 16, align: 'left' },
            ]
          });

          table.print(result.edges.map(e => ({
            ...e,
            other_name: e.direction === 'outgoing' ? e.to_ontology : e.from_ontology,
            score: e.score.toFixed(3),
          })));
        } catch (error: any) {
          console.error(colors.status.error('Failed to get ontology edges'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('reassign')
      .description('Move sources from one ontology to another. Updates s.document and SCOPED_BY edges. Refuses if source ontology is frozen.')
      .showHelpAfterError()
      .argument('<from>', 'Source ontology name')
      .requiredOption('--to <target>', 'Target ontology name')
      .requiredOption('--source-ids <ids...>', 'Source IDs to move')
      .action(async (from, options) => {
        try {
          const client = createClientFromEnv();
          const result = await client.reassignSources(from, options.to, options.sourceIds);

          console.log('\n' + separator());
          console.log(colors.status.success(`✓ Reassigned ${result.sources_reassigned} sources`));
          console.log(separator());
          console.log(`  ${colors.stats.label('From:')} ${result.from_ontology}`);
          console.log(`  ${colors.stats.label('To:')} ${result.to_ontology}`);
          console.log(`  ${colors.stats.label('Sources moved:')} ${coloredCount(result.sources_reassigned)}`);
          console.log(separator());
        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to reassign sources'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('dissolve')
      .description('Dissolve an ontology non-destructively. Moves all sources to the target ontology, then removes the Ontology node. Unlike delete, this preserves all data. Refuses if ontology is pinned or frozen.')
      .showHelpAfterError()
      .argument('<name>', 'Ontology to dissolve')
      .requiredOption('--into <target>', 'Target ontology to receive sources')
      .action(async (name, options) => {
        try {
          const client = createClientFromEnv();
          const result = await client.dissolveOntology(name, options.into);

          console.log('\n' + separator());
          console.log(colors.status.success(`✓ Dissolved ontology "${name}"`));
          console.log(separator());
          console.log(`  ${colors.stats.label('Sources reassigned:')} ${coloredCount(result.sources_reassigned)}`);
          console.log(`  ${colors.stats.label('Node deleted:')} ${result.ontology_node_deleted ? colors.status.success('yes') : colors.status.dim('no')}`);
          if (result.reassignment_targets.length > 0) {
            console.log(`  ${colors.stats.label('Targets:')} ${result.reassignment_targets.join(', ')}`);
          }
          console.log(separator());
        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to dissolve ontology'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('proposals')
      .description('List breathing proposals generated by the breathing cycle. Proposals are promotion or demotion suggestions for ontologies that require human review before execution.')
      .option('--status <status>', 'Filter by status: pending, approved, rejected, expired')
      .option('--type <type>', 'Filter by type: promotion, demotion')
      .option('--ontology <name>', 'Filter by ontology name')
      .action(async (options) => {
        try {
          const client = createClientFromEnv();
          const result = await client.listProposals({
            status: options.status,
            proposal_type: options.type,
            ontology: options.ontology,
          });

          if (result.count === 0) {
            console.log(colors.status.warning('\n⚠ No proposals found'));
            return;
          }

          console.log('\n' + colors.ui.title('📋 Breathing Proposals'));
          console.log(separator());

          for (const p of result.proposals) {
            const typeIcon = p.proposal_type === 'promotion' ? '⬆' : '⬇';
            const statusColor = p.status === 'pending' ? colors.status.warning
              : p.status === 'approved' ? colors.status.success
              : p.status === 'rejected' ? colors.status.error
              : colors.status.dim;

            console.log(`  ${colors.ui.key(`#${p.id}`)} ${typeIcon} ${colors.evidence.document(p.ontology_name)} ${statusColor(`[${p.status}]`)}`);
            console.log(`    ${colors.status.dim(p.reasoning.substring(0, 120))}${p.reasoning.length > 120 ? '...' : ''}`);

            if (p.proposal_type === 'promotion' && p.anchor_concept_id) {
              console.log(`    ${colors.stats.label('Anchor:')} ${p.anchor_concept_id}`);
            }
            if (p.proposal_type === 'demotion' && p.target_ontology) {
              console.log(`    ${colors.stats.label('Target:')} ${p.target_ontology}`);
            }
            if (p.protection_score !== null && p.protection_score !== undefined) {
              console.log(`    ${colors.stats.label('Scores:')} mass=${p.mass_score?.toFixed(3)} coherence=${p.coherence_score?.toFixed(3)} protection=${p.protection_score?.toFixed(3)}`);
            }
            console.log(`    ${colors.stats.label('Epoch:')} ${p.created_at_epoch}  ${colors.stats.label('Created:')} ${new Date(p.created_at).toLocaleString()}`);
            console.log();
          }

          console.log(separator());
          console.log(`  ${coloredCount(result.count)} proposal${result.count !== 1 ? 's' : ''}`);
        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to list proposals'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('proposal')
      .description('View or review a specific breathing proposal.')
      .argument('<id>', 'Proposal ID')
      .option('--approve', 'Approve this proposal')
      .option('--reject', 'Reject this proposal')
      .option('--notes <notes>', 'Review notes')
      .action(async (id, options) => {
        try {
          const client = createClientFromEnv();
          const proposalId = parseInt(id, 10);

          if (options.approve || options.reject) {
            const status = options.approve ? 'approved' as const : 'rejected' as const;
            const result = await client.reviewProposal(proposalId, status, options.notes);
            console.log('\n' + separator());
            console.log(colors.status.success(`✓ Proposal #${proposalId} ${status}`));
            if (options.notes) {
              console.log(`  ${colors.stats.label('Notes:')} ${options.notes}`);
            }
            console.log(separator());
            return;
          }

          // View proposal details
          const p = await client.getProposal(proposalId);
          const typeIcon = p.proposal_type === 'promotion' ? '⬆ Promotion' : '⬇ Demotion';
          const statusColor = p.status === 'pending' ? colors.status.warning
            : p.status === 'approved' ? colors.status.success
            : p.status === 'rejected' ? colors.status.error
            : colors.status.dim;

          console.log('\n' + colors.ui.title(`📋 Proposal #${p.id}: ${typeIcon}`));
          console.log(separator());
          console.log(`  ${colors.stats.label('Ontology:')} ${colors.evidence.document(p.ontology_name)}`);
          console.log(`  ${colors.stats.label('Status:')} ${statusColor(p.status)}`);
          console.log(`  ${colors.stats.label('Reasoning:')} ${p.reasoning}`);

          if (p.anchor_concept_id) {
            console.log(`  ${colors.stats.label('Anchor Concept:')} ${p.anchor_concept_id}`);
          }
          if (p.target_ontology) {
            console.log(`  ${colors.stats.label('Absorption Target:')} ${p.target_ontology}`);
          }

          if (p.mass_score !== null && p.mass_score !== undefined) {
            console.log(`  ${colors.stats.label('Mass:')} ${p.mass_score.toFixed(4)}`);
          }
          if (p.coherence_score !== null && p.coherence_score !== undefined) {
            console.log(`  ${colors.stats.label('Coherence:')} ${p.coherence_score.toFixed(4)}`);
          }
          if (p.protection_score !== null && p.protection_score !== undefined) {
            console.log(`  ${colors.stats.label('Protection:')} ${p.protection_score.toFixed(4)}`);
          }

          console.log(`  ${colors.stats.label('Epoch:')} ${p.created_at_epoch}`);
          console.log(`  ${colors.stats.label('Created:')} ${new Date(p.created_at).toLocaleString()}`);

          if (p.reviewed_at) {
            console.log(`  ${colors.stats.label('Reviewed:')} ${new Date(p.reviewed_at).toLocaleString()} by ${p.reviewed_by}`);
          }
          if (p.reviewer_notes) {
            console.log(`  ${colors.stats.label('Notes:')} ${p.reviewer_notes}`);
          }

          console.log(separator());

          if (p.status === 'pending') {
            console.log(colors.status.dim('  Use --approve or --reject to review this proposal'));
          }
        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to get proposal'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('breathe')
      .description('Trigger a breathing cycle. Scores all ontologies, recomputes centroids, identifies candidates, and generates proposals for review. Use --dry-run to preview candidates without generating proposals.')
      .option('--dry-run', 'Preview candidates without generating proposals')
      .option('--demotion-threshold <threshold>', 'Protection score below which to consider demotion', '0.15')
      .option('--promotion-min-degree <degree>', 'Minimum concept degree for promotion candidacy', '10')
      .option('--max-proposals <count>', 'Maximum proposals per cycle', '5')
      .action(async (options) => {
        try {
          const client = createClientFromEnv();

          console.log('\n' + colors.ui.title('🫁 Running Breathing Cycle'));
          if (options.dryRun) {
            console.log(colors.status.dim('  (dry run — no proposals will be generated)'));
          }
          console.log();

          const result = await client.triggerBreathingCycle({
            dry_run: options.dryRun || false,
            demotion_threshold: parseFloat(options.demotionThreshold),
            promotion_min_degree: parseInt(options.promotionMinDegree, 10),
            max_proposals: parseInt(options.maxProposals, 10),
          });

          console.log(separator());
          console.log(`  ${colors.stats.label('Epoch:')} ${result.cycle_epoch}`);
          console.log(`  ${colors.stats.label('Ontologies scored:')} ${coloredCount(result.scores_updated)}`);
          console.log(`  ${colors.stats.label('Centroids updated:')} ${coloredCount(result.centroids_updated)}`);
          console.log(`  ${colors.stats.label('Demotion candidates:')} ${coloredCount(result.demotion_candidates)}`);
          console.log(`  ${colors.stats.label('Promotion candidates:')} ${coloredCount(result.promotion_candidates)}`);
          console.log(`  ${colors.stats.label('Proposals generated:')} ${coloredCount(result.proposals_generated)}`);
          console.log(`  ${colors.stats.label('Dry run:')} ${result.dry_run ? 'yes' : 'no'}`);
          console.log(separator());

          if (result.proposals_generated > 0) {
            console.log(colors.status.dim('  Use `kg ontology proposals` to review proposals'));
          }
        } catch (error: any) {
          console.error(colors.status.error('✗ Breathing cycle failed'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  );
