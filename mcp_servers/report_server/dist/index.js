#!/usr/bin/env node
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { CallToolRequestSchema, ListToolsRequestSchema, } from '@modelcontextprotocol/sdk/types.js';
import nodemailer from 'nodemailer';
import React from 'react';
import { render } from '@react-email/render';
// Import env for system name and email configuration
const env = {
    SYSTEM_NAME: process.env.SYSTEM_NAME || 'HPC',
    EMAIL_RECIPIENT: process.env.EMAIL_RECIPIENT || 'help+delta@ncsa.illinois.edu'
};
/**
 * React Email template for the conversation HTML report
 */
const ConversationEmail = ({ messages, systemInfo, reportType }) => (React.createElement("html", null, React.createElement("head", null, React.createElement("meta", { charSet: 'utf-8' }), React.createElement("title", null, `${env.SYSTEM_NAME} ${reportType || 'Report'}`), React.createElement("style", null, `
        body { font-family: Arial, sans-serif; padding: 20px; line-height: 1.6; }
        .header { background-color: #f4f4f4; padding: 15px; border-radius: 5px; margin-bottom: 20px; }
        .message { margin-bottom: 15px; padding: 10px; border-left: 3px solid #007acc; }
        .user { border-left-color: #28a745; }
        .assistant { border-left-color: #007acc; }
        .system { border-left-color: #ffc107; background-color: #fff9c4; }
        .role { font-weight: bold; color: #333; }
        .content { margin-top: 5px; white-space: pre-wrap; }
        .system-info { background-color: #e9ecef; padding: 15px; border-radius: 5px; margin-top: 20px; }
      `)), React.createElement("body", null, React.createElement("div", { className: "header" }, React.createElement("h1", null, `${env.SYSTEM_NAME} ${reportType || 'Report'}`), React.createElement("p", null, `Generated on: ${new Date().toISOString()}`)), React.createElement("div", { className: "conversation" }, messages.map((msg, i) => (React.createElement("div", {
    key: i,
    className: `message ${msg.role}`
}, React.createElement("div", { className: "role" }, `${msg.role.toUpperCase()}:`), React.createElement("div", { className: "content" }, msg.content))))), systemInfo && React.createElement("div", { className: "system-info" }, React.createElement("h3", null, "System Information"), React.createElement("pre", null, systemInfo)))));
/**
 * MCP Server for sending reports from HPC support conversations
 */
class ReportServer {
    server;
    constructor() {
        this.server = new Server({
            name: 'report-server',
            version: '1.0.0',
        }, {
            capabilities: {
                tools: {},
            },
        });
        this.setupToolHandlers();
        // Error handling
        this.server.onerror = (error) => console.error('[MCP Error]', error);
        process.on('SIGINT', async () => {
            await this.server.close();
            process.exit(0);
        });
    }
    setupToolHandlers() {
        // List available tools
        this.server.setRequestHandler(ListToolsRequestSchema, async () => {
            return {
                tools: [
                    {
                        name: 'send_support_report',
                        description: `Send a support report email with conversation history to the ${env.SYSTEM_NAME} support team`,
                        inputSchema: {
                            type: 'object',
                            properties: {
                                messages: {
                                    type: 'array',
                                    description: 'Array of conversation messages',
                                    items: {
                                        type: 'object',
                                        properties: {
                                            role: { type: 'string', description: 'Message role (user/assistant/system)' },
                                            content: { type: 'string', description: 'Message content' }
                                        },
                                        required: ['role', 'content']
                                    }
                                },
                                report_type: {
                                    type: 'string',
                                    description: 'Type of report (Issue Report, Bug Report, Feature Request, etc.)',
                                    default: 'Support Report'
                                }
                            },
                            required: ['messages']
                        }
                    }
                ]
            };
        });
        // Handle tool calls
        this.server.setRequestHandler(CallToolRequestSchema, async (request) => {
            const { name, arguments: args } = request.params;
            try {
                switch (name) {
                    case 'send_support_report':
                        return await this.sendSupportReport(args);
                    default:
                        throw new Error(`Unknown tool: ${name}`);
                }
            }
            catch (error) {
                const errorMessage = error instanceof Error ? error.message : String(error);
                return {
                    content: [
                        {
                            type: 'text',
                            text: `Error: ${errorMessage}`
                        }
                    ]
                };
            }
        });
    }
    async sendSupportReport(args) {
        const { messages, report_type = 'Support Report' } = args;
        if (!messages || !Array.isArray(messages)) {
            throw new Error('Messages array is required');
        }
        // Use environment variable for recipient
        const recipient = env.EMAIL_RECIPIENT;
        // Add system information to the report
        const systemInfoText = this.getSystemInfo();
        // Create email content with normal priority
        const subject = `${env.SYSTEM_NAME} ${report_type}`;
        const plainText = this.createPlainTextReport(messages, systemInfoText, report_type);
        const htmlContent = await render(React.createElement(ConversationEmail, {
            messages,
            systemInfo: systemInfoText,
            reportType: report_type
        }));
        await this.sendEmail({
            to: recipient,
            subject,
            text: plainText,
            html: htmlContent
        });
        return {
            content: [
                {
                    type: 'text',
                    text: `Support report sent successfully to ${recipient}\nSubject: ${subject}`
                }
            ]
        };
    }
    createPlainTextReport(messages, additionalInfo = '', reportType = 'Report') {
        let report = `${env.SYSTEM_NAME} ${reportType}\n`;
        report += `Generated: ${new Date().toISOString()}\n`;
        report += '='.repeat(50) + '\n\n';
        report += 'CONVERSATION HISTORY:\n';
        report += '-'.repeat(25) + '\n';
        messages.forEach((msg, i) => {
            report += `\n[${i + 1}] ${msg.role.toUpperCase()}:\n${msg.content}\n`;
        });
        if (additionalInfo) {
            report += '\n' + '='.repeat(50) + '\n';
            report += 'ADDITIONAL INFORMATION:\n';
            report += '-'.repeat(25) + '\n';
            report += additionalInfo + '\n';
        }
        return report;
    }
    getSystemInfo() {
        const info = [];
        info.push(`Research System: ${env.SYSTEM_NAME}`);
        info.push(`Hostname: ${process.env.HOSTNAME}`);
        info.push(`Working Directory: ${process.env.PWD}`);
        info.push(`Reporter: ${process.env.USER}`);
        info.push(`Timestamp: ${new Date().toLocaleString('en-US', { timeZone: 'UTC' })}`);
        return info.join('\n');
    }
    async sendEmail(options) {
        // Create transporter using sendmail (same as EmailCommand)
        const transporter = nodemailer.createTransport({
            sendmail: true,
            newline: 'unix',
            path: '/usr/sbin/sendmail',
        });
        const fromEmail = process.env.EMAIL_FROM || `noreply@${env.SYSTEM_NAME.toLowerCase()}.ncsa.illinois.edu`;
        await transporter.sendMail({
            from: fromEmail,
            to: options.to,
            subject: options.subject,
            text: options.text,
            html: options.html,
        });
    }
    async run() {
        const transport = new StdioServerTransport();
        await this.server.connect(transport);
        console.error('Report MCP server running on stdio');
    }
}
const server = new ReportServer();
server.run().catch(console.error);
//# sourceMappingURL=index.js.map