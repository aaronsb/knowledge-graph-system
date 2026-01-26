/**
 * System and database formatters
 */

export function formatDatabaseStats(result: any): string {
  let output = `# Database Statistics\n\n`;

  if (result.graph_name) {
    output += `Graph: ${result.graph_name}\n\n`;
  }

  output += `## Nodes\n\n`;
  output += `Concepts: ${result.concept_count?.toLocaleString() || 0}\n`;
  output += `Sources: ${result.source_count?.toLocaleString() || 0}\n`;
  output += `Instances: ${result.instance_count?.toLocaleString() || 0}\n`;
  output += `Total: ${result.total_node_count?.toLocaleString() || 0}\n\n`;

  output += `## Relationships\n\n`;
  output += `Total: ${result.total_edge_count?.toLocaleString() || 0}\n\n`;

  if (result.ontologies && result.ontologies.length > 0) {
    output += `## Ontologies (${result.ontologies.length})\n\n`;
    result.ontologies.forEach((ont: any, idx: number) => {
      output += `${idx + 1}. ${ont.ontology_name} (${ont.concept_count} concepts)\n`;
    });
  }

  return output;
}

export function formatDatabaseInfo(result: any): string {
  let output = `# Database Information\n\n`;

  if (result.database) {
    output += `Database: ${result.database}\n`;
  }
  if (result.version) {
    output += `PostgreSQL: ${result.version}\n`;
  }
  if (result.age_version) {
    output += `Apache AGE: ${result.age_version}\n`;
  }
  if (result.graph_name) {
    output += `Graph: ${result.graph_name}\n`;
  }

  return output;
}

export function formatDatabaseHealth(result: any): string {
  let output = `# Database Health\n\n`;

  const status = result.status || result.healthy;
  if (status === 'healthy' || status === true) {
    output += `Status: ✓ Healthy\n`;
  } else {
    output += `Status: ✗ Unhealthy\n`;
  }

  if (result.graph_available !== undefined) {
    output += `Graph Available: ${result.graph_available ? '✓ Yes' : '✗ No'}\n`;
  }

  if (result.connection) {
    output += `Connection: ${result.connection}\n`;
  }

  return output;
}

export function formatSystemStatus(result: any): string {
  let output = `# System Status\n\n`;

  if (result.scheduler) {
    output += `## Job Scheduler\n\n`;
    output += `Status: ${result.scheduler.running ? '✓ Running' : '✗ Stopped'}\n`;
    if (result.scheduler.active_jobs !== undefined) {
      output += `Active Jobs: ${result.scheduler.active_jobs}\n`;
    }
    if (result.scheduler.pending_jobs !== undefined) {
      output += `Pending Jobs: ${result.scheduler.pending_jobs}\n`;
    }
    output += `\n`;
  }

  if (result.resources) {
    output += `## Resource Usage\n\n`;
    if (result.resources.cpu_percent !== undefined) {
      output += `CPU: ${result.resources.cpu_percent}%\n`;
    }
    if (result.resources.memory_percent !== undefined) {
      output += `Memory: ${result.resources.memory_percent}%\n`;
    }
    if (result.resources.disk_percent !== undefined) {
      output += `Disk: ${result.resources.disk_percent}%\n`;
    }
  }

  return output;
}

export function formatApiHealth(result: any): string {
  let output = `# API Health\n\n`;

  if (result.status === 'healthy' || result.healthy === true) {
    output += `Status: ✓ Healthy\n`;
  } else {
    output += `Status: ✗ Unhealthy\n`;
  }

  if (result.timestamp) {
    output += `Timestamp: ${new Date(result.timestamp).toLocaleString()}\n`;
  }

  if (result.version) {
    output += `Version: ${result.version}\n`;
  }

  return output;
}

export function formatMcpAllowedPaths(result: any): string {
  if (!result.configured) {
    let output = `# MCP File Access Allowlist\n\n`;
    output += `Status: ✗ Not Configured\n\n`;
    if (result.message) {
      output += `${result.message}\n\n`;
    }
    if (result.hint) {
      output += `Hint: ${result.hint}\n`;
    }
    return output;
  }

  let output = `# MCP File Access Allowlist\n\n`;
  output += `Status: ✓ Configured\n`;
  output += `Version: ${result.version}\n\n`;

  if (result.allowed_directories && result.allowed_directories.length > 0) {
    output += `## Allowed Directories (${result.allowed_directories.length})\n\n`;
    result.allowed_directories.forEach((dir: string, idx: number) => {
      output += `${idx + 1}. ${dir}\n`;
    });
    output += `\n`;
  }

  if (result.allowed_patterns && result.allowed_patterns.length > 0) {
    output += `## Allowed Patterns (${result.allowed_patterns.length})\n\n`;
    result.allowed_patterns.forEach((pattern: string, idx: number) => {
      output += `${idx + 1}. ${pattern}\n`;
    });
    output += `\n`;
  }

  if (result.blocked_patterns && result.blocked_patterns.length > 0) {
    output += `## Blocked Patterns (${result.blocked_patterns.length})\n\n`;
    result.blocked_patterns.forEach((pattern: string, idx: number) => {
      output += `${idx + 1}. ${pattern}\n`;
    });
    output += `\n`;
  }

  output += `## Limits\n\n`;
  output += `Max File Size: ${result.max_file_size_mb} MB\n`;
  output += `Max Files Per Directory: ${result.max_files_per_directory}\n`;

  if (result.config_path) {
    output += `\nConfig Path: ${result.config_path}\n`;
  }

  return output;
}
