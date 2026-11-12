import React, { useState, useEffect } from 'react';
import { FolderGit2, Plus, RefreshCw, Calendar } from 'lucide-react';
import { projectsApi } from '../../api/projects';
import { Project } from '../../types';
import { Card, CardHeader, CardBody } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Modal } from '../../components/ui/Modal';
import { Input, Textarea } from '../../components/ui/Input';
import { Badge } from '../../components/ui/Badge';
import { LoadingSpinner } from '../../components/ui/LoadingSpinner';
import { EmptyState } from '../../components/ui/EmptyState';
import { useAuth } from '../../context/AuthContext';

export const ProjectsPage: React.FC = () => {
  const { isViewer } = useAuth();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [name, setName] = useState('');
  const [slug, setSlug] = useState('');
  const [description, setDescription] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const fetchData = async () => {
    setLoading(true);
    try {
      const data = await projectsApi.list();
      setProjects(data);
    } catch (err: any) {
      console.error('Failed to load projects', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleCreate = async () => {
    if (!name.trim()) {
      alert('Project name is required.');
      return;
    }
    setSubmitting(true);
    setErrorMsg(null);
    try {
      await projectsApi.create({
        name: name.trim(),
        slug: slug.trim() || undefined,
        description: description.trim() || undefined,
      });
      setModalOpen(false);
      setName('');
      setSlug('');
      setDescription('');
      await fetchData();
    } catch (err: any) {
      setErrorMsg(err.response?.data?.detail || err.message || 'Failed to create project');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-surface-200 dark:border-surface-800 pb-5">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-surface-900 dark:text-white">
              Projects & Workspaces
            </h1>
            <Badge variant="purple" size="sm">
              <FolderGit2 className="w-3 h-3 mr-1" />
              {projects.length} Active
            </Badge>
          </div>
          <p className="text-sm text-surface-500 dark:text-surface-400 mt-1">
            Segment services, incidents, and investigation workflows across distinct business initiatives.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button variant="outline" size="sm" onClick={fetchData} loading={loading}>
            <RefreshCw className="w-4 h-4 mr-1.5" />
            Refresh
          </Button>

          <Button
            variant="primary"
            size="sm"
            onClick={() => setModalOpen(true)}
            disabled={isViewer}
            title={isViewer ? 'Requires Engineer role or higher' : undefined}
          >
            <Plus className="w-4 h-4 mr-1.5" />
            New Project
          </Button>
        </div>
      </div>

      {loading ? (
        <div className="py-16 flex justify-center">
          <LoadingSpinner size="lg" />
        </div>
      ) : projects.length === 0 ? (
        <Card>
          <EmptyState
            title="No projects configured"
            message="Organize your platform by creating a project for your services and incidents."
            action={
              !isViewer ? (
                <Button variant="primary" size="sm" onClick={() => setModalOpen(true)}>
                  <Plus className="w-4 h-4 mr-1.5" /> Create Project
                </Button>
              ) : undefined
            }
          />
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {projects.map((proj) => (
            <Card key={proj.id} className="hover:border-surface-400 dark:hover:border-surface-600 transition-colors">
              <CardHeader>
                <div className="flex items-start justify-between">
                  <div className="w-8 h-8 rounded-lg bg-brand-500/10 text-brand-500 flex items-center justify-center">
                    <FolderGit2 className="w-4 h-4" />
                  </div>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-surface-100 dark:bg-surface-800 text-surface-600 dark:text-surface-400">
                    {proj.slug || proj.id.slice(0, 8)}
                  </span>
                </div>
                <h3 className="text-base font-semibold text-surface-900 dark:text-white mt-3">
                  {proj.name}
                </h3>
              </CardHeader>

              <CardBody className="space-y-3">
                <p className="text-xs text-surface-600 dark:text-surface-400 min-h-[32px] line-clamp-2">
                  {proj.description || 'No project description provided.'}
                </p>

                <div className="pt-3 border-t border-surface-200 dark:border-surface-800 flex items-center justify-between text-[11px] text-surface-500">
                  <span className="flex items-center gap-1">
                    <Calendar className="w-3.5 h-3.5" />
                    {new Date(proj.created_at).toLocaleDateString()}
                  </span>
                  <span className="font-mono text-[10px]">Org: {proj.organization_id?.slice(0, 8) || 'Global'}</span>
                </div>
              </CardBody>
            </Card>
          ))}
        </div>
      )}

      {/* Create Project Modal */}
      <Modal isOpen={modalOpen} onClose={() => setModalOpen(false)} title="Create New Project">
        <div className="space-y-4 text-sm">
          {errorMsg && (
            <div className="p-3 rounded-lg bg-danger-500/10 border border-danger-500/20 text-danger-500 text-xs">
              {errorMsg}
            </div>
          )}

          <Input
            label="Project Name *"
            placeholder="e.g. Core Infrastructure"
            value={name}
            onChange={(e) => {
              setName(e.target.value);
              if (!slug) {
                setSlug(
                  e.target.value
                    .toLowerCase()
                    .replace(/\s+/g, '-')
                    .replace(/[^a-z0-9-]/g, '')
                );
              }
            }}
          />

          <Input
            label="Slug Identifier"
            placeholder="e.g. core-infra"
            value={slug}
            onChange={(e) => setSlug(e.target.value)}
          />

          <Textarea
            label="Description (Optional)"
            rows={2}
            placeholder="Scope and purpose of this project..."
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />

          <div className="flex justify-end gap-3 pt-3 border-t border-surface-200 dark:border-surface-800">
            <Button variant="ghost" onClick={() => setModalOpen(false)}>
              Cancel
            </Button>
            <Button variant="primary" onClick={handleCreate} loading={submitting}>
              Create Project
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
};
