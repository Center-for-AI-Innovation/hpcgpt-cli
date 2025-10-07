# Report MCP Server

A Model Context Protocol (MCP) server that provides reporting functionality for HPC support conversations. This server enables AI assistants to send structured email reports containing conversation history and system information to the HPC support team.

## Features

### Available Tools

#### `send_support_report`
Send a structured support report to the HPC support team with conversation history and system information.

**Parameters:**
- `messages` (required, array): Array of conversation messages with role and content
- `report_type` (optional, string): Type of report (default: "Support Report")

**Example:**
```json
{
  "name": "send_support_report",
  "arguments": {
    "messages": [
      {"role": "user", "content": "I'm having trouble submitting SLURM jobs"},
      {"role": "assistant", "content": "Let me help you troubleshoot that..."}
    ],
    "report_type": "Issue Report"
  }
}
```

**Note:** The recipient email is automatically configured via the `EMAIL_RECIPIENT` environment variable, and system information is automatically collected.

## Installation

### Prerequisites
- Node.js >= 18
- Bun runtime
- Access to system sendmail (typically `/usr/sbin/sendmail`)
- Proper email configuration on the host system

### Setup

1. **Install dependencies:**
   ```bash
   cd mcp_servers/report_server
   bun install
   ```

2. **Build the server:**
   ```bash
   bun run build
   ```

3. **Set up environment variables (optional):**
   ```bash
   export EMAIL_FROM="noreply@delta.ncsa.illinois.edu"
   ```

## Configuration

### OpenCode Integration

The server is configured in `opencode.jsonc`:

```json
{
  "mcp": {
    "report-server": {
      "type": "local",
      "command": ["bun", "run", "report-server", ">", "logs/report-server.log"],
      "enabled": true
    }
  },
  "command": {
    "report_issue": {
      "template": "Use the send_support_report tool to send an issue report to the HPC support team. This report will contain the full conversation history and system information about where the report originated.",
      "description": "Report an issue to the HPC support team",
      "agent": "support",
      "model": "ncsaollama/qwen3:32b"
    }
  }
}
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SYSTEM_NAME` | Name of the HPC system | `HPC` |
| `EMAIL_RECIPIENT` | Support team email address | `help+delta@ncsa.illinois.edu` |
| `EMAIL_FROM` | From email address | `noreply@{system_name}.ncsa.illinois.edu` |

## Usage

### Running the Server

```bash
# Development mode
bun run dev

# Production mode
bun run start

# Via OpenCode MCP (recommended)
bun run report-server
```

### Email Templates

The server generates both plain text and HTML email reports:

#### HTML Features:
- Professional styling with color-coded message types
- Responsive design
- System information section
- Timestamp and metadata
- Role-based message formatting (user/assistant/system)

#### Plain Text Features:
- Structured conversation history
- System information section
- Clear message separation
- Timestamp and metadata

## Integration with HPC Support Workflow

### Support Report Process:
1. User interacts with HPC support chatbot
2. Issue requires human attention or escalation
3. Chatbot uses `send_support_report` tool
4. Structured email sent to HPC support team
5. Support team receives formatted report with full context

### Report Types:
- **Issue Report**: Technical problems requiring assistance
- **Bug Report**: Software or system bugs
- **Feature Request**: Requests for new functionality
- **General Inquiry**: Questions or information requests

### Priority Levels:
- **urgent**: Critical system issues affecting multiple users
- **high**: Important issues affecting individual users
- **normal**: Standard support requests (default)
- **low**: General questions or minor issues

## Architecture

### Project Structure:
```
report_server/
├── src/
│   └── index.ts          # Main MCP server implementation
├── dist/                 # Compiled JavaScript output
├── package.json          # Package configuration
├── tsconfig.json         # TypeScript configuration
└── README.md            # This file
```

### Key Components:
- **EmailReportServer**: Main MCP server class
- **ConversationEmail**: React email template component
- **Tool Handlers**: Implementation of MCP tools
- **Email Transport**: Nodemailer with sendmail integration

## Error Handling

The server includes comprehensive error handling for:

- **Missing Parameters**: Validates required fields
- **Email Transport Errors**: Handles sendmail failures
- **Template Rendering Errors**: Catches React rendering issues
- **System Information Gathering**: Safe environment variable access
- **Process Management**: Graceful shutdown on SIGINT

## Development

### Scripts

- `bun run build` - Compile TypeScript to JavaScript
- `bun run dev` - Run in development mode with watch
- `bun run start` - Run the compiled server
- `bun run report-server` - Run server for MCP integration

### Adding New Report Types

To add new report types:

1. Update the `send_support_report` tool schema
2. Modify the email template if needed
3. Add any specific formatting logic
4. Update documentation

### Customizing Email Templates

The React email template can be customized by modifying the `ConversationEmail` component. The template supports:

- Custom styling via embedded CSS
- Dynamic content based on report type
- System information formatting
- Message role-based styling

## Troubleshooting

### Common Issues

1. **"Sendmail not found"**
   - Ensure `/usr/sbin/sendmail` exists and is executable
   - Check system mail configuration
   - Verify postfix or similar MTA is installed

2. **"Permission denied"**
   - Check file permissions on sendmail
   - Verify user has mail sending privileges
   - Check SELinux/AppArmor policies if applicable

3. **"Email not delivered"**
   - Check system mail logs (`/var/log/maillog` or similar)
   - Verify recipient email addresses
   - Check spam filters and email routing

4. **"Template rendering failed"**
   - Ensure React and @react-email/render are installed
   - Check for syntax errors in email template
   - Verify message format matches expected schema

### Debug Mode

Enable debug logging by setting:
```bash
export DEBUG=report-server
```

### Testing

Test the server manually:
```bash
# Build and start server
bun run build
bun run start

# Test with sample data (in another terminal)
echo '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"send_support_report","arguments":{"messages":[{"role":"user","content":"test message"}]}}}' | bun run start
```

## Security Considerations

- **Email Content**: All conversation history is included in emails
- **System Information**: Automatic gathering includes environment details
- **Recipient Validation**: Ensure recipient addresses are authorized
- **Rate Limiting**: Consider implementing rate limits for abuse prevention

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/new-feature`
3. Make your changes and test thoroughly
4. Update documentation as needed
5. Commit your changes: `git commit -am 'Add new feature'`
6. Push to the branch: `git push origin feature/new-feature`
7. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Support

For support and questions:
- Check the HPC system documentation
- Contact the HPC support team
- File issues in the project repository

---

**Note**: This MCP server is designed for use with HPC systems. Ensure proper email configuration and permissions before deployment.

