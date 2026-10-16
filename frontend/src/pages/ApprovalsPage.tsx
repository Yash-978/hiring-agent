import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { useQuery } from "@tanstack/react-query";
import { apiRequest, type Approval } from "@/api/client";

const statusColors: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  pending: "default",
  approved: "secondary",
  rejected: "destructive",
};

export function ApprovalsPage() {
  const { data: approvals, isLoading, error } = useQuery({
    queryKey: ["approvals"],
    queryFn: () => apiRequest<Approval[]>("/approvals"),
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  if (error) {
    return (
      <Card>
        <CardContent className="text-center py-8 text-destructive">
          Failed to load approvals: {error instanceof Error ? error.message : "Unknown error"}
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="p-6 space-y-4">
      <CardHeader>
        <CardTitle>Approvals</CardTitle>
      </CardHeader>
      <Card>
        <CardContent>
          {!approvals?.length ? (
            <div className="text-center py-8 text-muted-foreground">
              No approvals found.
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Action</TableHead>
                  <TableHead>Target</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Requested By</TableHead>
                  <TableHead>Decided By</TableHead>
                  <TableHead>Created</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {approvals?.map((approval) => (
                  <TableRow key={approval.id}>
                    <TableCell>{approval.action_type}</TableCell>
                    <TableCell>
                      {approval.target_type} #{approval.target_id}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={statusColors[approval.status] ?? "outline"}
                      >
                        {approval.status}
                      </Badge>
                    </TableCell>
                    <TableCell>{approval.requested_by}</TableCell>
                    <TableCell>{approval.decided_by_user_id ?? "—"}</TableCell>
                    <TableCell>{new Date(approval.created_at).toLocaleDateString()}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}