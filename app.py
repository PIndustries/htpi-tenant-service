"""HTPI Tenant Service - Manages multi-tenant organizations"""

import os
import asyncio
import json
import logging
from datetime import datetime
import nats
from nats.aio.client import Client as NATS
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
NATS_URL = os.environ.get('NATS_URL', 'nats://localhost:4222')
NATS_USER = os.environ.get('NATS_USER')
NATS_PASSWORD = os.environ.get('NATS_PASSWORD')

# Mock tenant database (in production, this would come from MongoDB via htpi-mongodb-service)
MOCK_TENANTS = {
    'tenant-001': {
        'id': 'tenant-001',
        'name': 'Mercy General Hospital',
        'status': 'active',
        'settings': {
            'claimmd_accounts': [
                {
                    'id': 'claimmd-001',
                    'name': 'Primary Account',
                    'api_key': 'encrypted_key_here'
                }
            ],
            'features': ['patients', 'claims', 'insurance', 'encounters']
        },
        'created_at': '2024-01-01T00:00:00Z'
    },
    'tenant-002': {
        'id': 'tenant-002',
        'name': 'Springfield Clinic',
        'status': 'active',
        'settings': {
            'claimmd_accounts': [
                {
                    'id': 'claimmd-002',
                    'name': 'Main Account',
                    'api_key': 'encrypted_key_here'
                },
                {
                    'id': 'claimmd-003',
                    'name': 'Billing Account',
                    'api_key': 'encrypted_key_here'
                }
            ],
            'features': ['patients', 'claims', 'insurance']
        },
        'created_at': '2024-01-15T00:00:00Z'
    }
}

# User-tenant mappings (in production, would be in MongoDB)
USER_TENANT_ACCESS = {
    'user-cust-001': ['tenant-001', 'tenant-002'],  # demo@htpi.com
    'user-cust-002': ['tenant-001'],  # john@example.com
    'user-admin-001': '*'  # admin@htpi.com can access all
}

class TenantService:
    def __init__(self):
        self.nc = None
        
    async def connect(self):
        """Connect to NATS"""
        try:
            # Build connection options
            options = {}
            if NATS_USER and NATS_PASSWORD:
                options['user'] = NATS_USER
                options['password'] = NATS_PASSWORD
            
            self.nc = await nats.connect(NATS_URL, **options)
            logger.info(f"Connected to NATS at {NATS_URL}")
            
            # Subscribe to tenant requests
            await self.nc.subscribe("htpi.tenant.create", cb=self.handle_create_tenant)
            await self.nc.subscribe("htpi.tenant.update", cb=self.handle_update_tenant)
            await self.nc.subscribe("htpi.tenant.list", cb=self.handle_list_tenants)
            await self.nc.subscribe("htpi.tenant.get", cb=self.handle_get_tenant)
            await self.nc.subscribe("htpi.tenant.list.for.user", cb=self.handle_list_user_tenants)
            await self.nc.subscribe("htpi.tenant.verify.access", cb=self.handle_verify_access)
            
            logger.info("Tenant service subscriptions established")
        except Exception as e:
            logger.error(f"Failed to connect to NATS: {str(e)}")
            raise
    
    async def handle_create_tenant(self, msg):
        """Handle tenant creation requests"""
        try:
            data = json.loads(msg.data.decode())
            client_id = data.get('clientId')
            
            # Create new tenant
            tenant_id = f"tenant-{len(MOCK_TENANTS) + 1:03d}"
            new_tenant = {
                'id': tenant_id,
                'name': data.get('name'),
                'status': 'active',
                'settings': {
                    'claimmd_accounts': [],
                    'features': data.get('features', ['patients', 'claims', 'insurance'])
                },
                'created_at': datetime.utcnow().isoformat()
            }
            
            # Add to mock database
            MOCK_TENANTS[tenant_id] = new_tenant
            
            # Send response
            await self.nc.publish(f"admin.tenant.response.{client_id}", 
                json.dumps({
                    'success': True,
                    'tenant': new_tenant,
                    'clientId': client_id
                }).encode())
            
            logger.info(f"Created tenant: {tenant_id}")
            
        except Exception as e:
            logger.error(f"Error in handle_create_tenant: {str(e)}")
            await self.nc.publish(f"admin.tenant.response.{data.get('clientId')}", 
                json.dumps({
                    'success': False,
                    'error': str(e),
                    'clientId': data.get('clientId')
                }).encode())
    
    async def handle_update_tenant(self, msg):
        """Handle tenant update requests"""
        try:
            data = json.loads(msg.data.decode())
            tenant_id = data.get('tenantId')
            client_id = data.get('clientId')
            
            if tenant_id not in MOCK_TENANTS:
                await self.nc.publish(f"admin.tenant.response.{client_id}", 
                    json.dumps({
                        'success': False,
                        'error': 'Tenant not found',
                        'clientId': client_id
                    }).encode())
                return
            
            # Update tenant
            tenant = MOCK_TENANTS[tenant_id]
            if 'name' in data:
                tenant['name'] = data['name']
            if 'status' in data:
                tenant['status'] = data['status']
            if 'settings' in data:
                tenant['settings'].update(data['settings'])
            
            # Send response
            await self.nc.publish(f"admin.tenant.response.{client_id}", 
                json.dumps({
                    'success': True,
                    'tenant': tenant,
                    'clientId': client_id
                }).encode())
            
            logger.info(f"Updated tenant: {tenant_id}")
            
        except Exception as e:
            logger.error(f"Error in handle_update_tenant: {str(e)}")
    
    async def handle_list_tenants(self, msg):
        """Handle list all tenants requests (admin only)"""
        try:
            data = json.loads(msg.data.decode())
            client_id = data.get('clientId')
            
            # Return all tenants for admin
            tenants = list(MOCK_TENANTS.values())
            
            await self.nc.publish(f"admin.tenant.response.{client_id}", 
                json.dumps({
                    'success': True,
                    'tenants': tenants,
                    'clientId': client_id
                }).encode())
            
        except Exception as e:
            logger.error(f"Error in handle_list_tenants: {str(e)}")
    
    async def handle_list_user_tenants(self, msg):
        """Handle list tenants for specific user"""
        try:
            data = json.loads(msg.data.decode())
            user_id = data.get('userId')
            client_id = data.get('clientId')
            portal = data.get('portal', 'customer')
            
            # Get user's accessible tenants
            access = USER_TENANT_ACCESS.get(user_id, [])
            
            if access == '*':
                # Admin has access to all
                tenants = list(MOCK_TENANTS.values())
            else:
                # Filter tenants by access
                tenants = [MOCK_TENANTS[tid] for tid in access if tid in MOCK_TENANTS]
            
            # Send to appropriate portal channel
            channel = f"{portal}.tenants.response.{client_id}"
            await self.nc.publish(channel, 
                json.dumps({
                    'success': True,
                    'tenants': tenants,
                    'clientId': client_id
                }).encode())
            
            logger.info(f"Listed {len(tenants)} tenants for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error in handle_list_user_tenants: {str(e)}")
    
    async def handle_get_tenant(self, msg):
        """Handle get single tenant request"""
        try:
            data = json.loads(msg.data.decode())
            tenant_id = data.get('tenantId')
            client_id = data.get('clientId')
            portal = data.get('portal', 'customer')
            
            tenant = MOCK_TENANTS.get(tenant_id)
            
            if not tenant:
                channel = f"{portal}.tenant.response.{client_id}"
                await self.nc.publish(channel, 
                    json.dumps({
                        'success': False,
                        'error': 'Tenant not found',
                        'clientId': client_id
                    }).encode())
                return
            
            # Send tenant data
            channel = f"{portal}.tenant.response.{client_id}"
            await self.nc.publish(channel, 
                json.dumps({
                    'success': True,
                    'tenant': tenant,
                    'clientId': client_id
                }).encode())
            
        except Exception as e:
            logger.error(f"Error in handle_get_tenant: {str(e)}")
    
    async def handle_verify_access(self, msg):
        """Verify user has access to a tenant"""
        try:
            data = json.loads(msg.data.decode())
            user_id = data.get('userId')
            tenant_id = data.get('tenantId')
            
            # Check access
            access = USER_TENANT_ACCESS.get(user_id, [])
            has_access = access == '*' or tenant_id in access
            
            await msg.respond(json.dumps({
                'hasAccess': has_access,
                'userId': user_id,
                'tenantId': tenant_id
            }).encode())
            
        except Exception as e:
            logger.error(f"Error in handle_verify_access: {str(e)}")
            await msg.respond(json.dumps({
                'hasAccess': False,
                'error': str(e)
            }).encode())
    
    async def run(self):
        """Run the service"""
        await self.connect()
        logger.info("Tenant service is running...")
        
        # Keep service running
        try:
            await asyncio.Future()  # Run forever
        except KeyboardInterrupt:
            pass
        finally:
            await self.nc.close()

async def main():
    """Main entry point"""
    service = TenantService()
    await service.run()

if __name__ == '__main__':
    asyncio.run(main())