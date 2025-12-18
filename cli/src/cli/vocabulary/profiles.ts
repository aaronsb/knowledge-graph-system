/**
 * Vocabulary Profiles Commands
 * Aggressiveness profile management (Bezier curves for consolidation behavior)
 */

import { Command } from 'commander';
import { createClientFromEnv } from '../../api/client';
import * as colors from '../colors';
import { coloredCount, separator } from '../colors';

export function createProfilesCommand(): Command {
  const profilesCommand = new Command('profiles')
    .description('Manage aggressiveness profiles (Bezier curves for consolidation behavior)');

  // kg vocab profiles list
  profilesCommand.addCommand(
    new Command('list')
      .description('List all aggressiveness profiles including builtin (8 predefined) and custom profiles. Shows profile name, control points, description, and builtin flag.')
      .action(async () => {
        try {
          const client = createClientFromEnv();

          console.log('\n' + separator());
          console.log(colors.ui.title('🎨 Aggressiveness Profiles'));
          console.log(separator());

          const result = await client.listAggressivenessProfiles();

          console.log(`\n  ${colors.stats.label('Total Profiles:')} ${coloredCount(result.total)}`);
          console.log(`  ${colors.stats.label('Builtin:')} ${coloredCount(result.builtin)}`);
          console.log(`  ${colors.stats.label('Custom:')} ${coloredCount(result.custom)}`);

          console.log(`\n${colors.stats.section('Profiles')}`);

          for (const profile of result.profiles) {
            const builtinFlag = profile.is_builtin ? colors.status.dim(' [B]') : '';
            console.log(`\n  ${colors.ui.value(profile.profile_name)}${builtinFlag}`);
            console.log(`    ${colors.stats.label('Control Points:')} (${profile.control_x1.toFixed(2)}, ${profile.control_y1.toFixed(2)}) (${profile.control_x2.toFixed(2)}, ${profile.control_y2.toFixed(2)})`);
            console.log(`    ${colors.stats.label('Description:')} ${colors.status.dim(profile.description)}`);
          }

          console.log('\n' + separator());

        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to list aggressiveness profiles'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  );

  // kg vocab profiles show <name>
  profilesCommand.addCommand(
    new Command('show')
      .description('Show details for a specific aggressiveness profile including Bezier parameters and timestamps.')
      .argument('<name>', 'Profile name')
      .action(async (name: string) => {
        try {
          const client = createClientFromEnv();

          console.log('\n' + separator());
          console.log(colors.ui.title(`🎨 Profile: ${name}`));
          console.log(separator());

          const profile = await client.getAggressivenessProfile(name);

          console.log(`\n  ${colors.stats.label('Profile Name:')} ${colors.ui.value(profile.profile_name)}`);
          console.log(`  ${colors.stats.label('Builtin:')} ${profile.is_builtin ? colors.status.success('Yes') : colors.ui.value('No')}`);

          console.log(`\n${colors.stats.section('Bezier Curve Parameters')}`);
          console.log(`  ${colors.stats.label('Control Point 1:')} (${colors.ui.value(profile.control_x1.toFixed(2))}, ${colors.ui.value(profile.control_y1.toFixed(2))})`);
          console.log(`  ${colors.stats.label('Control Point 2:')} (${colors.ui.value(profile.control_x2.toFixed(2))}, ${colors.ui.value(profile.control_y2.toFixed(2))})`);

          console.log(`\n${colors.stats.section('Description')}`);
          console.log(`  ${colors.status.dim(profile.description)}`);

          if (profile.created_at) {
            console.log(`\n${colors.stats.section('Metadata')}`);
            console.log(`  ${colors.stats.label('Created:')} ${colors.status.dim(new Date(profile.created_at).toLocaleString())}`);
            if (profile.updated_at) {
              console.log(`  ${colors.stats.label('Updated:')} ${colors.status.dim(new Date(profile.updated_at).toLocaleString())}`);
            }
          }

          console.log('\n' + separator());

        } catch (error: any) {
          console.error(colors.status.error(`✗ Failed to get profile: ${name}`));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  );

  // kg vocab profiles create
  profilesCommand.addCommand(
    new Command('create')
      .description('Create a custom aggressiveness profile with Bezier curve parameters.')
      .requiredOption('--name <name>', 'Profile name (3-50 chars)')
      .requiredOption('--x1 <n>', 'First control point X (0.0-1.0)', parseFloat)
      .requiredOption('--y1 <n>', 'First control point Y (-2.0 to 2.0)', parseFloat)
      .requiredOption('--x2 <n>', 'Second control point X (0.0-1.0)', parseFloat)
      .requiredOption('--y2 <n>', 'Second control point Y (-2.0 to 2.0)', parseFloat)
      .requiredOption('--description <desc>', 'Profile description (min 10 chars)')
      .action(async (options) => {
        try {
          const client = createClientFromEnv();

          console.log('\n' + separator());
          console.log(colors.ui.title('🎨 Creating Aggressiveness Profile'));
          console.log(separator());

          console.log(`\n  ${colors.stats.label('Name:')} ${colors.ui.value(options.name)}`);
          console.log(`  ${colors.stats.label('Control Point 1:')} (${colors.ui.value(options.x1.toFixed(2))}, ${colors.ui.value(options.y1.toFixed(2))})`);
          console.log(`  ${colors.stats.label('Control Point 2:')} (${colors.ui.value(options.x2.toFixed(2))}, ${colors.ui.value(options.y2.toFixed(2))})`);
          console.log(`  ${colors.stats.label('Description:')} ${colors.status.dim(options.description)}`);

          const profile = await client.createAggressivenessProfile({
            profile_name: options.name,
            control_x1: options.x1,
            control_y1: options.y1,
            control_x2: options.x2,
            control_y2: options.y2,
            description: options.description
          });

          console.log('\n' + colors.status.success('✓ Profile created successfully'));
          console.log(`\n  ${colors.stats.label('Profile Name:')} ${colors.ui.value(profile.profile_name)}`);
          console.log(`  ${colors.stats.label('Created:')} ${colors.status.dim(new Date(profile.created_at).toLocaleString())}`);

          console.log('\n' + separator());

        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to create aggressiveness profile'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  );

  // kg vocab profiles delete <name>
  profilesCommand.addCommand(
    new Command('delete')
      .description('Delete a custom aggressiveness profile. Cannot delete builtin profiles.')
      .argument('<name>', 'Profile name to delete')
      .action(async (name: string) => {
        try {
          const client = createClientFromEnv();

          console.log('\n' + separator());
          console.log(colors.ui.title('🗑️  Deleting Aggressiveness Profile'));
          console.log(separator());

          console.log(`\n  ${colors.stats.label('Profile:')} ${colors.ui.value(name)}`);

          const result = await client.deleteAggressivenessProfile(name);

          console.log('\n' + colors.status.success('✓ Profile deleted successfully'));
          console.log(`\n  ${colors.stats.label('Message:')} ${colors.status.dim(result.message)}`);

          console.log('\n' + separator());

        } catch (error: any) {
          console.error(colors.status.error(`✗ Failed to delete profile: ${name}`));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  );

  return profilesCommand;
}
