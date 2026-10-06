import os
import json
import re
import logging
import argparse
import shlex
from getpass import getpass, getuser
from typing import Optional
from rich_argparse import RichHelpFormatter
from fastmcp import FastMCP

import splunklib.client as client
import splunklib.results as results
import pandas as pd

from src.config import Config, consolidate_config_and_args
from src.logging import route_fastmcp_logs_to_root, setup_logging

class SplunkMCP(FastMCP):
    """
    Splunk MCP Server for querying Splunk data.
    """
    def __init__(self, name: str, args: argparse.Namespace):
        super().__init__(name)
        self.splunk_host = args.splunk_host
        self.splunk_port = args.splunk_port
        
        self.add_tool(self.splunk_search)
        self.add_tool(self.reframe_apptests)
        self.add_tool(self.reframe_perflogs)
        self.add_tool(self.lmod_module_usage)
        self.add_tool(self.software_install_report)

    def _get_splunk_service(self) -> client.Service:
        """
        Connects to the Splunk service using stored credentials or environment variables.
        """
        token = os.environ.get("SPLUNK_TOKEN")
        if token:
            return client.connect(host=self.splunk_host, port=self.splunk_port, token=token)

        user = os.environ.get("SPLUNK_USERNAME") or getuser()
        password = os.environ.get("SPLUNK_PASSWORD")

        if not password:
            # For MCP server, we need to handle this differently
            # Return an error message prompting for environment setup
            raise RuntimeError(
                "SPLUNK_PASSWORD environment variable not set. "
                "Please set SPLUNK_USERNAME and SPLUNK_PASSWORD environment variables, "
                "or set SPLUNK_TOKEN for token-based authentication."
            )

        return client.connect(host=self.splunk_host, port=self.splunk_port, username=user, password=password)

    def _parse_time_range(self, earliest: str, latest: str, days: Optional[int]) -> tuple:
        """
        Extracts and processes the earliest and latest time from arguments.
        """
        if earliest:
            earliest = earliest.replace("\\", "")
        else:
            earliest = "-7d@d"
            
        if latest:
            latest = latest.replace("\\", "")
        else:
            latest = "now"

        if days:
            earliest = f"-{days}d@d"
            latest = "now"
        
        return earliest, latest

    async def splunk_search(
        self,
        search: str,
        earliest: str = "-7d@d",
        latest: str = "now",
        days: Optional[int] = None
    ) -> str:
        """
        Execute a Splunk search query and return the results.

        Args:
            search: The Splunk search string to execute (e.g., "index=main | head 5").
            earliest: Earliest time in the search range (e.g., -1h, -7d@d). Default: -7d@d
            latest: Latest time in the search range (e.g., now, @d). Default: now
            days: Shortcut to search from N days ago until now. Overrides earliest and latest.

        Returns:
            The search results in JSON format.
        """
        try:
            earliest_time, latest_time = self._parse_time_range(earliest, latest, days)
            service = self._get_splunk_service()
            
            search_result = service.jobs.oneshot(
                f"search {search}",
                earliest_time=earliest_time,
                latest_time=latest_time,
                output_mode='json'
            )
            reader = results.JSONResultsReader(search_result)
            
            results_list = []
            for result in reader:
                if isinstance(result, dict):
                    results_list.append(result)
            
            return json.dumps(results_list, indent=2)
        except Exception as e:
            return f"Error executing Splunk search: {str(e)}"

    async def reframe_apptests(
        self,
        system: str = "",
        status: Optional[str] = None,
        earliest: str = "-7d@d",
        latest: str = "now",
        days: Optional[int] = None,
        json_output: bool = False,
        csv_output: bool = False
    ) -> str:
        """
        Generate a report for Reframe application tests from Splunk logs.

        Args:
            system: Filter by system/host name prefix (e.g., "pitzer", "cardinal").
            status: Filter by test status (e.g., "PASS", "FAIL", "CANCEL").
            earliest: Earliest time for the search (Splunk format). Default: -7d@d
            latest: Latest time for the search (Splunk format). Default: now
            days: Search from N days ago until now (overrides earliest and latest).
            json_output: Output in JSON format.
            csv_output: Output in CSV format.

        Returns:
            Reframe test results in table, JSON, or CSV format.
        """
        import re

        def parse_event(event: dict) -> Optional[dict]:
            """Parse Reframe test event fields from Splunk result."""
            raw = event.get('_raw', '')
            if 'package=' not in raw:
                return None

            entry = {'system': event.get('system', '')}

            # Extract system from host if not set
            if not entry['system'] and 'host' in event:
                entry['system'] = re.sub(r'-.*', '', event['host'])

            # Extract fields
            for field in ['package', 'version', 'date']:
                m = re.search(rf'{field}=(\S+)', raw)
                entry[field] = m.group(1) if m else ''

            # failed_tests can be quoted with spaces
            m = re.search(r"failed_tests='([^']*)'", raw)
            if m:
                entry['failed_tests'] = m.group(1)
            else:
                m = re.search(r"failed_tests=(\S+)", raw)
                entry['failed_tests'] = m.group(1) if m else ''

            # deps can be quoted
            m = re.search(r"deps=('?)([^'\s]+(?:\s+[^'\s]+)*)(\1)", raw)
            if m:
                entry['deps'] = m.group(2).strip()
            else:
                entry['deps'] = ''

            # status can be quoted or unquoted
            m = re.search(r"status=('?)([^'\s]+(?:\s+[^'\s]+)*)(\1)", raw)
            if m:
                entry['status'] = m.group(2).strip()
            else:
                entry['status'] = ''

            return entry

        try:
            earliest_time, latest_time = self._parse_time_range(earliest, latest, days)
            service = self._get_splunk_service()

            # Minimal Splunk search - just fetch raw events
            search = f"search (process=reframe_apptest OR reframe_regression_test) host={system}*"
            
            search_result = service.jobs.oneshot(
                search,
                earliest_time=earliest_time,
                latest_time=latest_time,
                output_mode='json'
            )
            data = results.JSONResultsReader(search_result)

            records = []
            for event in data:
                if isinstance(event, dict):
                    parsed = parse_event(event)
                    if parsed:
                        records.append(parsed)

            if not records:
                return "No Reframe test results found."

            df = pd.DataFrame(records)
            df = df.rename(columns={'deps': 'dependencies', 'failed_tests': 'failed tests'})
            df = df[['system', 'package', 'version', 'dependencies', 'status', 'failed tests', 'date']]

            # Deduplicate and sort
            df = df.drop_duplicates(subset=['system', 'package', 'version', 'dependencies'], keep='first')
            df = df.sort_values(['status', 'system', 'package', 'version', 'dependencies'])
            
            if status:
                df = df[df["status"] == status]

            if json_output:
                output_records = df.replace({float('nan'): None}).to_dict('records')
                return json.dumps(output_records, indent=2)

            if csv_output:
                return df.to_csv(index=False)

            return df.to_string(index=False)
        except Exception as e:
            return f"Error retrieving Reframe test results: {str(e)}"

    async def reframe_perflogs(
        self,
        system: str = "",
        partition: str = "",
        name: str = "",
        earliest: str = "-7d@d",
        latest: str = "now",
        days: Optional[int] = None,
        raw_output: bool = False,
        average: bool = False,
        json_output: bool = False,
        csv_output: bool = False
    ) -> str:
        """
        Analyze Reframe performance logs from Splunk.

        Args:
            system: Filter by system name (e.g., "pitzer", "cardinal").
            partition: Filter by partition name (e.g., "gpu", "cpu").
            name: Filter by test name pattern.
            earliest: Earliest time for the search (Splunk format). Default: -7d@d
            latest: Latest time for the search (Splunk format). Default: now
            days: Search from N days ago until now (overrides earliest and latest).
            raw_output: Show raw parsed records.
            average: Show average result for tests with same name, system, progenv, modules.
            json_output: Output in JSON format.
            csv_output: Output in CSV format.

        Returns:
            Reframe performance data in table, JSON, or CSV format.
        """
        LOG_PATTERN = re.compile(
            r'<\d+>(\d{4}-\d{2}-\d{2}T[\d:.+-]+)\s+\S+\s+reframe_perflogs\[\d+\]:\s+'
            r'reframe=(\S+)\s+system=(\S+)\s+partition=(\S+)\s+name="([^"]+)"\s+'
            r'jobid=(\d+)\s+environ=(\S+)\s+nodelist=([\w,]+)\s+modules="([^"]*)"\s+'
            r'value=([\d.]+)\s+unit=(\S+)\s+ref=([\d.]+)\s+l=(\S+)\s+u=([\d.]+)'
        )

        def parse_line(line):
            """Parse a single log line into a dict."""
            m = LOG_PATTERN.match(line)
            if not m:
                return None
            ts, reframe_ver, sys_name, part, test_name, jobid, environ, nodes, modules, value, unit, ref, l, u = m.groups()
            return {
                'timestamp': ts,
                'reframe_version': reframe_ver,
                'system': sys_name,
                'partition': part,
                'name': test_name,
                'jobid': int(jobid),
                'environ': environ,
                'nodes': nodes.split(','),
                'modules': modules,
                'value': float(value),
                'unit': unit,
                'ref': float(ref) if ref != 'None' else None,
                'lower_bound': float(l) if l != 'None' else None,
                'upper_bound': float(u) if u != 'None' else None,
            }

        try:
            earliest_time, latest_time = self._parse_time_range(earliest, latest, days)
            service = self._get_splunk_service()

            search = f"search reframe_perflogs"
            if system:
                search += f" system={system}*"
            if partition:
                search += f" partition={partition}*"
            if name:
                search += f" name=\"*{name}*\""

            search_result = service.jobs.oneshot(
                search,
                earliest_time=earliest_time,
                latest_time=latest_time,
                output_mode='json'
            )
            data = results.JSONResultsReader(search_result)

            records = []
            for item in data:
                if isinstance(item, dict) and '_raw' in item:
                    record = parse_line(item['_raw'])
                    if record:
                        records.append(record)

            if raw_output:
                return json.dumps(records, indent=2)

            # Group records for averaging if requested
            if average:
                from collections import defaultdict
                groups = defaultdict(list)
                for r in records:
                    key = (r['name'], r['system'], r['partition'], r['environ'], r['modules'])
                    groups[key].append(r)
                
                records = []
                for key, group in groups.items():
                    first = group[0]
                    avg_value = sum(r['value'] for r in group) / len(group)
                    
                    if first['ref'] is not None:
                        lower = first['lower_bound']
                        upper = first['upper_bound']
                        if lower is not None or upper is not None:
                            low = first['ref'] * (1 - lower) if lower is not None else None
                            high = first['ref'] * (1 + upper) if upper is not None else None
                            if (low is None or avg_value >= low) and (high is None or avg_value <= high):
                                result = "pass"
                            else:
                                result = "fail"
                        else:
                            result = "n/a"
                    else:
                        result = "n/a"
                    
                    records.append({
                        'name': first['name'],
                        'system': f"{first['system']}:{first['partition']}",
                        'progenv': first['environ'],
                        'modules': first['modules'],
                        'unit': first['unit'],
                        'value': avg_value,
                        'ref': first['ref'],
                        'result': result,
                        'job_nodelist': f"{len(group)} runs",
                        'jobid': f"{len(group)} jobs",
                    })

            if json_output:
                output_records = []
                for r in records:
                    system_field = r.get('system')
                    if ':' not in system_field:
                        system_field = f"{system_field}:{r['partition']}"
                    progenv = r.get('progenv') or r.get('environ', '')
                    modules = r['modules']
                    pval = r['value']
                    pref = r['ref']
                    job_nodelist = r.get('job_nodelist') or ','.join(r.get('nodes', []))
                    jobid = r.get('jobid') or str(r.get('jobid', ''))
                    result = r.get('result', 'n/a')

                    if average:
                        output_records.append({
                            'name': r['name'],
                            'system': system_field,
                            'progenv': progenv,
                            'modules': modules,
                            'unit': r['unit'],
                            'value': pval,
                            'ref': pref,
                            'runs': job_nodelist,
                            'result': result,
                        })
                    else:
                        output_records.append({
                            'name': r['name'],
                            'system': system_field,
                            'progenv': progenv,
                            'modules': modules,
                            'unit': r['unit'],
                            'value': pval,
                            'ref': pref,
                            'job_nodelist': job_nodelist,
                            'jobid': jobid,
                            'result': result,
                        })
                return json.dumps(output_records, indent=2)

            if csv_output:
                import csv
                from io import StringIO
                output = StringIO()
                fieldnames = ['name', 'system', 'progenv', 'modules', 'unit', 'value', 'ref', 'result']
                if not average:
                    fieldnames.extend(['job_nodelist', 'jobid'])
                
                writer = csv.DictWriter(output, fieldnames=fieldnames)
                writer.writeheader()
                
                for r in records:
                    system_field = r.get('system')
                    if ':' not in system_field:
                        system_field = f"{system_field}:{r['partition']}"
                    progenv = r.get('progenv') or r.get('environ', '')
                    
                    row = {
                        'name': r['name'],
                        'system': system_field,
                        'progenv': progenv,
                        'modules': r['modules'],
                        'unit': r['unit'],
                        'value': r['value'],
                        'ref': r['ref'],
                        'result': r.get('result', 'n/a'),
                    }
                    if not average:
                        row['job_nodelist'] = r.get('job_nodelist') or ','.join(r.get('nodes', []))
                        row['jobid'] = r.get('jobid') or str(r.get('jobid', ''))
                    writer.writerow(row)
                return output.getvalue()

            # Table output
            if average:
                lines = [
                    f"{'name':<35} {'system':<20} {'progenv':<15} {'modules':<30} {'unit':<8} {'val':>8} {'ref':>7} {'runs':<38} {'result':<10}",
                    "-" * 191
                ]
                for r in records:
                    lines.append(
                        f"{r['name']:<35} {r['system']:<20} {r['progenv']:<15} "
                        f"{r['modules']:<30} {r['unit']:<8} {r['value']:>8.2f} "
                        f"{r['ref']:>7.0f} {r['job_nodelist']:<38} {r['result']:<10}"
                    )
            else:
                lines = [
                    f"{'name':<35} {'system':<20} {'progenv':<15} {'modules':<30} {'unit':<8} {'val':>8} {'ref':>7} {'job_nodelist':<38} {'jobid':<35} {'result':<10}",
                    "-" * 221
                ]
                for r in records:
                    lines.append(
                        f"{r['name']:<35} {r['system']:<20} {r['progenv']:<15} "
                        f"{r['modules']:<30} {r['unit']:<8} {r['value']:>8.2f} "
                        f"{r['ref']:>7.0f} {','.join(r['nodes']):<38} {r['jobid']:<35} {r.get('result', 'n/a'):<10}"
                    )
            
            return "\n".join(lines)
        except Exception as e:
            return f"Error retrieving Reframe performance logs: {str(e)}"

    async def lmod_module_usage(
        self,
        system: str = "*",
        module: str = "*",
        user: str = "*",
        earliest: str = "-7d@d",
        latest: str = "now",
        days: Optional[int] = None,
        top: int = 20,
        allnodes: bool = False,
        byuser: bool = False,
        allmods: bool = False,
        raw: bool = False,
        showjobnums: bool = False,
        debug: bool = False
    ) -> str:
        """
        Report Lmod module usage stats from Splunk.

        Args:
            system: Target system name (e.g., "pitzer", "cardinal"). Default: *
            module: Filter by module name (glob patterns supported). Default: *
            user: Filter by specific username. Default: *
            earliest: Earliest time in Splunk range. Default: -7d@d
            latest: Latest time in Splunk range. Default: now
            days: Search the last N days (overrides earliest and latest).
            top: Number of top results to show. Default: 20
            allnodes: Include login/vis nodes (default: compute nodes only).
            byuser: Break down usage statistics by individual username.
            allmods: Aggregate counts across all selected modules instead of by path.
            raw: Show raw Splunk search results.
            showjobnums: Show actual job numbers instead of count.
            debug: Print the generated Splunk search query for debugging.

        Returns:
            Module usage statistics in table or JSON format.
        """
        try:
            earliest_time, latest_time = self._parse_time_range(earliest, latest, days)
            service = self._get_splunk_service()

            if byuser:
                user_stats = "by module path user"
            elif allmods:
                user_stats = "dc(user) as n_users"
            else:
                user_stats = "dc(user) as n_users by module path"

            if showjobnums:
                jobnum_stats = "list(jobnum) as jobnums"
            else:
                jobnum_stats = "dc(jobnum) as n_jobs"

            host_type = "" if allnodes else "jobnum=*"

            search_parts = [
                f"search process=ModuleUsageTracking lmodhost={system} module={module} user={user} {host_type}",
                f"stats count {jobnum_stats} {user_stats}",
                "sort count desc",
                f"head {top}"
            ]

            if debug:
                debug_info = f"Generated search: {'|'.join(search_parts)}\n\n"
            else:
                debug_info = ""

            search_result = service.jobs.oneshot(
                "|".join(search_parts),
                earliest_time=earliest_time,
                latest_time=latest_time,
                output_mode='json'
            )
            data = results.JSONResultsReader(search_result)
            records = [item for item in data if isinstance(item, dict)]

            if raw:
                return debug_info + json.dumps(records, indent=2)

            if showjobnums:
                for r in records:
                    if 'jobnums' in r and isinstance(r['jobnums'], list):
                        r['jobnums'] = ','.join(str(j) for j in dict.fromkeys(r['jobnums']))

            pd.set_option("max_colwidth", 200)
            df = pd.DataFrame(records)
            
            return debug_info + df.to_string()
        except Exception as e:
            return f"Error retrieving Lmod module usage stats: {str(e)}"

    async def software_install_report(
        self,
        system: str = "*",
        package: str = "*",
        days: Optional[int] = 14
    ) -> str:
        """
        Generate a report for software installations from Splunk logs.

        Args:
            system: Filter by system/host name prefix (e.g., "pitzer", "cardinal"). Default: *
            package: Filter by package name (glob patterns supported). Default: *
            days: Search the last N days. Default: 14

        Returns:
            Software installation records in table format.
        """
        import re
        
        INSTALL_PATTERN = re.compile(
            r'system=(\S+)\s+package=(\S+)\s+version=(\S+)\s+dep=\'?(\S+)\'?\s+status=(\S+)'
        )

        def parse_event(event: dict) -> Optional[dict]:
            """Parse installation event fields from Splunk result."""
            raw = event.get('_raw', '')
            match = INSTALL_PATTERN.search(raw)
            if not match:
                return None
            
            sys_name, pkg, ver, dep, status = match.groups()
            
            # Normalize system name
            for pattern, replacement in [
                ('pitzer.*', 'pitzer'),
                ('ascend.*', 'ascend'),
                ('cardinal.*', 'cardinal')
            ]:
                sys_name = re.sub(pattern, replacement, sys_name)
            
            return {
                'system': sys_name,
                'package': pkg,
                'version': ver,
                'dep': dep[:100] if len(dep) > 100 else dep,
                'status': status,
            }

        try:
            earliest_time, latest_time = self._parse_time_range("-7d@d", "now", days)
            service = self._get_splunk_service()

            search = f"search (process=install-script OR process=*spack-install) host={system}*"

            search_result = service.jobs.oneshot(
                search,
                earliest_time=earliest_time,
                latest_time=latest_time,
                output_mode='json'
            )
            data = results.JSONResultsReader(search_result)
            
            records = []
            for event in data:
                if isinstance(event, dict):
                    parsed = parse_event(event)
                    if parsed:
                        records.append(parsed)

            if not records:
                return "No software installations found."

            df = pd.DataFrame(records)
            
            # Deduplicate by system, package, version, dep
            df = df.drop_duplicates(subset=['system', 'package', 'version', 'dep'])
            
            # Aggregate by system
            aggregated = df.groupby('system').agg({
                'package': lambda x: list(x),
                'version': lambda x: list(x),
                'dep': lambda x: list(x),
                'status': lambda x: list(x)
            }).reset_index()
            
            # Filter by package if specified
            if package != "*":
                mask = aggregated['package'].apply(
                    lambda x: any(package in str(p) for p in x) if isinstance(x, list) else package in str(x)
                )
                aggregated = aggregated[mask]

            pd.set_option("max_colwidth", 200)
            return aggregated.to_string()
        except Exception as e:
            return f"Error retrieving software installation report: {str(e)}"


def parse_command_line() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Splunk MCP Server",
        formatter_class=RichHelpFormatter,
    )
    parser.add_argument("-c", "--config",
        type=str,
        default="config.json",
    )   
    parser.add_argument("--host",
        type=str,
        help="Option to set the host the server will listen on.",
    )
    parser.add_argument("--port",
        type=int,
        help="Option to set the port the server will listen on.",
    )
    parser.add_argument("--log-file",
        type=str,
        help="Option to set the file logging will output to.",
    )
    parser.add_argument("-v","--verbose",
        action="store_true",
        help="Flag to change the log level of the console from INFO to DEBUG",
    )
    parser.add_argument("-t","--transport",
        type=str,
        help="Option to set the transport used to communicate between the client and server",
        choices=['stdio', 'streamable-http', 'http', 'sse'],
        default='stdio',
    )
    parser.add_argument("--splunk-host",
        type=str,
        help="Splunk server hostname",
    )
    parser.add_argument("--splunk-port",
        type=int,
        help="Splunk management port",
    )

    return parser.parse_args()


def main(args: argparse.Namespace) -> None:
    file_log_level = logging.DEBUG if args.verbose else logging.INFO
    console_log_level = None
    setup_logging(
        args.log_file,
        log_level=file_log_level,
        console_log_level=console_log_level,
        use_color=True,
        writemode="a",
    )
    route_fastmcp_logs_to_root(file_log_level)

    server = SplunkMCP("Splunk MCP Server", args)
    if args.transport == 'stdio':
        server.run(
            transport=args.transport,
            log_level=None,
        )
    else:
        server.run(
            transport=args.transport,
            host=args.host,
            port=args.port,
            log_level=None,
            uvicorn_config={"log_config": None}
        )


if __name__ == "__main__":
    # Load config and args
    args = parse_command_line()
    config = Config.load_from_json(args.config)
    args = consolidate_config_and_args(config, args)

    main(args)
